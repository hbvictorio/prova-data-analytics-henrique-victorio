# -*- coding: utf-8 -*-
"""
===============================================================================
 ANÁLISE DE DADOS - VITIVINICULTURA BRASILEIRA (EMBRAPA / VITIBRASIL)
===============================================================================
 Prova Substitutiva - POSTECH Data Analytics - Fase 1

 Objetivo:
   Analisar os dados de EXPORTAÇÃO e IMPORTAÇÃO de três categorias de
   produtos (Vinhos de mesa, Espumantes e Sucos de uva) a partir da base
   oficial da Embrapa Vitivinicultura (Vitibrasil), respondendo às
   perguntas de negócio dos diretores da empresa de vinhos.

 Fonte de dados:
   http://vitibrasil.cnpuv.embrapa.br/index.php?opcao=opt_01
   Arquivos CSV oficiais disponíveis em:
   http://vitibrasil.cnpuv.embrapa.br/download/<arquivo>.csv

 Bibliotecas: pandas, matplotlib, seaborn, requests
===============================================================================
"""

import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

# -----------------------------------------------------------------------------
# 0. CONFIGURAÇÕES GERAIS
# -----------------------------------------------------------------------------
sns.set_theme(style="whitegrid")           # estilo visual dos gráficos
plt.rcParams["figure.dpi"] = 150           # resolução das figuras
plt.rcParams["font.family"] = "DejaVu Sans"

DATA_DIR = "data"        # pasta local onde os CSVs serão salvos
OUT_DIR = "graficos"     # pasta onde os gráficos serão exportados
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

BASE_URL = "http://vitibrasil.cnpuv.embrapa.br/download/"

# Mapeamento: nome amigável -> (arquivo CSV, fluxo)
ARQUIVOS = {
    ("Exportação", "Vinhos de mesa"):  "ExpVinho.csv",
    ("Exportação", "Espumantes"):      "ExpEspumantes.csv",
    ("Exportação", "Suco de uva"):     "ExpSuco.csv",
    ("Importação", "Vinhos de mesa"):  "ImpVinhos.csv",
    ("Importação", "Espumantes"):      "ImpEspumantes.csv",
    ("Importação", "Suco de uva"):     "ImpSuco.csv",
}

# -----------------------------------------------------------------------------
# 1. EXTRAÇÃO - Download dos arquivos CSV oficiais da Embrapa
# -----------------------------------------------------------------------------
def baixar_arquivos():
    """Baixa os 6 arquivos CSV (3 categorias x 2 fluxos) do site da Embrapa."""
    for (_, _), arquivo in ARQUIVOS.items():
        caminho = os.path.join(DATA_DIR, arquivo)
        if not os.path.exists(caminho):  # evita download repetido
            print(f"Baixando {arquivo}...")
            resp = requests.get(BASE_URL + arquivo, timeout=60)
            resp.raise_for_status()
            with open(caminho, "wb") as f:
                f.write(resp.content)
    print("Download concluído.\n")


# -----------------------------------------------------------------------------
# 2. TRANSFORMAÇÃO - Limpeza e padronização dos dados
# -----------------------------------------------------------------------------
# Estrutura original dos CSVs da Embrapa (separador TAB):
#   - Coluna 'Id' e 'País'
#   - Cada ANO aparece DUAS vezes: a 1ª ocorrência é a QUANTIDADE (Kg)
#     e a 2ª ocorrência é o VALOR (US$).
# A função abaixo transforma esse formato "wide" em formato "long" (tidy),
# com as colunas: País | Ano | Quantidade_kg | Valor_usd
# -----------------------------------------------------------------------------
def carregar_e_tratar(arquivo, fluxo, produto):
    """Lê um CSV da Embrapa e devolve DataFrame tidy com Kg e US$ por país/ano."""
    caminho = os.path.join(DATA_DIR, arquivo)
    df = pd.read_csv(caminho, sep="\t", encoding="utf-8")

    # Remove a coluna de Id, que não é necessária para a análise
    df = df.drop(columns=["Id"])

    # Identifica as colunas de anos. O pandas renomeia colunas duplicadas
    # automaticamente: '1970' (quantidade) e '1970.1' (valor).
    col_pais = df.columns[0]
    colunas_qtd = [c for c in df.columns[1:] if not c.endswith(".1")]
    colunas_val = [c for c in df.columns[1:] if c.endswith(".1")]

    # Constrói o DataFrame de QUANTIDADE (formato longo)
    qtd = df[[col_pais] + colunas_qtd].melt(
        id_vars=col_pais, var_name="Ano", value_name="Quantidade_kg")
    qtd["Ano"] = qtd["Ano"].astype(int)

    # Constrói o DataFrame de VALOR (formato longo)
    val = df[[col_pais] + colunas_val].melt(
        id_vars=col_pais, var_name="Ano", value_name="Valor_usd")
    val["Ano"] = val["Ano"].str.replace(".1", "", regex=False).astype(int)

    # Junta quantidade e valor em uma única tabela
    tidy = qtd.merge(val, on=[col_pais, "Ano"])
    tidy = tidy.rename(columns={col_pais: "Pais"})

    # Converte valores para numérico (valores ausentes '-' viram 0)
    for col in ["Quantidade_kg", "Valor_usd"]:
        tidy[col] = pd.to_numeric(tidy[col], errors="coerce").fillna(0)

    # Remove linhas agregadoras/não-países que distorceriam o ranking
    excluir = ["Total", "Outros", "Não consta na tabela", "Não declarados",
               "Outros(1)"]
    tidy = tidy[~tidy["Pais"].isin(excluir)]

    # Padroniza nomes de países (limpeza de espaços)
    tidy["Pais"] = tidy["Pais"].str.strip()

    # Adiciona colunas de contexto
    tidy["Fluxo"] = fluxo        # Exportação ou Importação
    tidy["Produto"] = produto    # Vinhos de mesa, Espumantes ou Suco de uva
    return tidy


def montar_base():
    """Consolida os 6 arquivos em um único DataFrame."""
    frames = []
    for (fluxo, produto), arquivo in ARQUIVOS.items():
        frames.append(carregar_e_tratar(arquivo, fluxo, produto))
    base = pd.concat(frames, ignore_index=True)
    return base


# -----------------------------------------------------------------------------
# 3. ANÁLISES - Perguntas de negócio
# -----------------------------------------------------------------------------
def pergunta_1_2(base):
    """
    P1: País com maior EXPORTAÇÃO de cada produto em todo o período.
    P2: País com maior IMPORTAÇÃO de cada produto em todo o período.
    Critério principal: Valor acumulado em US$ (também reportamos Kg).
    """
    print("=" * 79)
    print("P1 e P2 - PAÍSES LÍDERES (acumulado no período)")
    print("=" * 79)
    resultados = {}
    for fluxo in ["Exportação", "Importação"]:
        for produto in ["Vinhos de mesa", "Espumantes", "Suco de uva"]:
            sub = base[(base["Fluxo"] == fluxo) & (base["Produto"] == produto)]
            agg = (sub.groupby("Pais")[["Quantidade_kg", "Valor_usd"]]
                      .sum().sort_values("Valor_usd", ascending=False))
            lider_valor = agg.index[0]
            lider_kg = agg.sort_values("Quantidade_kg", ascending=False).index[0]
            resultados[(fluxo, produto)] = agg
            print(f"\n{fluxo} - {produto}:")
            print(f"  Líder em VALOR : {lider_valor} "
                  f"(US$ {agg.loc[lider_valor, 'Valor_usd']:,.0f} | "
                  f"{agg.loc[lider_valor, 'Quantidade_kg']:,.0f} Kg)")
            print(f"  Líder em VOLUME: {lider_kg} "
                  f"({agg.loc[lider_kg, 'Quantidade_kg']:,.0f} Kg | "
                  f"US$ {agg.loc[lider_kg, 'Valor_usd']:,.0f})")
            print("  Top 5 por valor:")
            print(agg.head(5).to_string())
    return resultados


def graficos_top_paises(base):
    """Gráficos de barras horizontais: Top 5 países por fluxo e produto."""
    for fluxo in ["Exportação", "Importação"]:
        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        cores = {"Vinhos de mesa": "#722F37",
                 "Espumantes": "#C9A227",
                 "Suco de uva": "#6B2FA0"}
        for ax, produto in zip(axes, ["Vinhos de mesa", "Espumantes",
                                      "Suco de uva"]):
            sub = base[(base["Fluxo"] == fluxo) & (base["Produto"] == produto)]
            top = (sub.groupby("Pais")["Valor_usd"].sum()
                     .sort_values(ascending=False).head(5) / 1e6)
            sns.barplot(x=top.values, y=top.index, ax=ax,
                        color=cores[produto])
            ax.set_title(f"{produto}", fontweight="bold")
            ax.set_xlabel("Valor acumulado (US$ milhões)")
            ax.set_ylabel("")
            for i, v in enumerate(top.values):
                ax.text(v, i, f" {v:,.1f}", va="center", fontsize=9)
        fig.suptitle(f"Top 5 países - {fluxo} acumulada (1970-2025) - "
                     f"Valor US$", fontsize=14, fontweight="bold")
        fig.tight_layout()
        nome = f"top5_paises_{fluxo.lower().replace('ç', 'c').replace('ã', 'a')}.png"
        fig.savefig(os.path.join(OUT_DIR, nome), bbox_inches="tight")
        plt.close(fig)
        print(f"Gráfico salvo: {nome}")


def pergunta_3_4(base):
    """
    P3: Tendência da EXPORTAÇÃO ao longo dos anos (gráfico de linhas).
    P4: Tendência da IMPORTAÇÃO ao longo dos anos (gráfico de linhas).
    """
    cores = {"Vinhos de mesa": "#722F37",
             "Espumantes": "#C9A227",
             "Suco de uva": "#6B2FA0"}
    for fluxo in ["Exportação", "Importação"]:
        serie = (base[base["Fluxo"] == fluxo]
                 .groupby(["Ano", "Produto"])["Valor_usd"].sum()
                 .reset_index())
        fig, ax = plt.subplots(figsize=(12, 6))
        for produto, cor in cores.items():
            s = serie[serie["Produto"] == produto]
            ax.plot(s["Ano"], s["Valor_usd"] / 1e6, label=produto,
                    color=cor, linewidth=2)
        ax.set_title(f"Tendência da {fluxo} por produto (1970-2025) - "
                     f"Valor US$", fontsize=14, fontweight="bold")
        ax.set_xlabel("Ano")
        ax.set_ylabel("Valor (US$ milhões)")
        ax.legend(title="Produto")
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
        fig.tight_layout()
        nome = f"tendencia_{fluxo.lower().replace('ç', 'c').replace('ã', 'a')}_valor.png"
        fig.savefig(os.path.join(OUT_DIR, nome), bbox_inches="tight")
        plt.close(fig)
        print(f"Gráfico salvo: {nome}")

        # Também geramos a tendência em VOLUME (Kg/Litros) para complementar
        serie_kg = (base[base["Fluxo"] == fluxo]
                    .groupby(["Ano", "Produto"])["Quantidade_kg"].sum()
                    .reset_index())
        fig, ax = plt.subplots(figsize=(12, 6))
        for produto, cor in cores.items():
            s = serie_kg[serie_kg["Produto"] == produto]
            ax.plot(s["Ano"], s["Quantidade_kg"] / 1e6, label=produto,
                    color=cor, linewidth=2)
        ax.set_title(f"Tendência da {fluxo} por produto (1970-2025) - "
                     f"Volume (milhões de Kg/L)", fontsize=14,
                     fontweight="bold")
        ax.set_xlabel("Ano")
        ax.set_ylabel("Volume (milhões de Kg/L)")
        ax.legend(title="Produto")
        fig.tight_layout()
        nome = f"tendencia_{fluxo.lower().replace('ç', 'c').replace('ã', 'a')}_volume.png"
        fig.savefig(os.path.join(OUT_DIR, nome), bbox_inches="tight")
        plt.close(fig)
        print(f"Gráfico salvo: {nome}")


def pergunta_7(base):
    """
    P7: Valor de exportação dos três produtos no ano mais recente da base.
    Gera gráfico de barras com os KPIs.
    """
    exp = base[base["Fluxo"] == "Exportação"]
    # Considera o último ano com dados efetivamente reportados (> 0)
    anos_com_dados = (exp.groupby("Ano")["Valor_usd"].sum())
    ano_recente = anos_com_dados[anos_com_dados > 0].index.max()

    kpi = (exp[exp["Ano"] == ano_recente]
           .groupby("Produto")[["Quantidade_kg", "Valor_usd"]].sum()
           .reindex(["Vinhos de mesa", "Espumantes", "Suco de uva"]))

    print("=" * 79)
    print(f"P7 - VALOR DE EXPORTAÇÃO NO ANO MAIS RECENTE DA BASE ({ano_recente})")
    print("=" * 79)
    print(kpi.to_string(float_format=lambda x: f"{x:,.0f}"))
    total = kpi["Valor_usd"].sum()
    print(f"\nTotal exportado ({ano_recente}): US$ {total:,.0f}")

    cores = ["#722F37", "#C9A227", "#6B2FA0"]
    fig, ax = plt.subplots(figsize=(9, 6))
    barras = ax.bar(kpi.index, kpi["Valor_usd"] / 1e6, color=cores)
    for barra, valor in zip(barras, kpi["Valor_usd"]):
        ax.text(barra.get_x() + barra.get_width() / 2,
                barra.get_height() + 0.1,
                f"US$ {valor/1e6:,.2f} mi", ha="center", fontweight="bold")
    ax.set_title(f"Valor de exportação por produto - {ano_recente}",
                 fontsize=14, fontweight="bold")
    ax.set_ylabel("Valor (US$ milhões)")
    fig.tight_layout()
    nome = "kpi_exportacao_ano_recente.png"
    fig.savefig(os.path.join(OUT_DIR, nome), bbox_inches="tight")
    plt.close(fig)
    print(f"Gráfico salvo: {nome}")
    return ano_recente, kpi


def balanca_comercial(base):
    """
    Análise complementar: balança comercial (Exportação - Importação)
    dos três produtos somados, em valor US$.
    """
    piv = (base.groupby(["Ano", "Fluxo"])["Valor_usd"].sum()
           .unstack(fill_value=0))
    piv["Saldo"] = piv.get("Exportação", 0) - piv.get("Importação", 0)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(piv.index, piv["Exportação"] / 1e6, label="Exportação",
            color="#2E7D32", linewidth=2)
    ax.plot(piv.index, piv["Importação"] / 1e6, label="Importação",
            color="#C62828", linewidth=2)
    ax.fill_between(piv.index, piv["Saldo"] / 1e6, 0, alpha=0.15,
                    color="#1565C0", label="Saldo (Exp - Imp)")
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_title("Balança comercial - Vinhos de mesa + Espumantes + Suco de uva"
                 " (1970-2025)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Ano")
    ax.set_ylabel("Valor (US$ milhões)")
    ax.legend()
    fig.tight_layout()
    nome = "balanca_comercial.png"
    fig.savefig(os.path.join(OUT_DIR, nome), bbox_inches="tight")
    plt.close(fig)
    print(f"Gráfico salvo: {nome}")
    return piv


# -----------------------------------------------------------------------------
# 4. EXECUÇÃO PRINCIPAL
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    baixar_arquivos()                      # 1) Extração
    base = montar_base()                   # 2) Transformação
    print("Base consolidada:", base.shape)
    print(base.head(), "\n")

    resultados = pergunta_1_2(base)        # P1 e P2
    graficos_top_paises(base)              # Gráficos de apoio P1/P2
    pergunta_3_4(base)                     # P3 e P4 (linhas)
    ano, kpi = pergunta_7(base)            # P7 (barras/KPI)
    piv = balanca_comercial(base)          # Análise complementar

    # Exporta a base tratada para conferência
    base.to_csv("base_consolidada_vitibrasil.csv", index=False)
    print("\nBase tratada exportada: base_consolidada_vitibrasil.csv")
    print("Análise concluída com sucesso!")
