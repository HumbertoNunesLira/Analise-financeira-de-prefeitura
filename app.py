"""Dashboard automatizado — despesas, receitas e licitações da Prefeitura de
Teixeira/PB. Dados via TCE-PB (dados-abertos.tce.pb.gov.br), atualizados
diariamente por pipeline/fetch.py + pipeline/transform.py (ver
.github/workflows/update-data.yml).

Projeto 3 — mesma linha analítica do Projeto 2 (analise.ipynb), agora com
gráficos interativos e dados atualizados sem intervenção manual.
"""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pipeline.style import CAT_PALETTE, GRID, INK, INK_MUTED, INK_SECONDARY, STATUS, SURFACE, fmt_reais, hex_to_rgba

DADOS_DIR = Path(__file__).resolve().parent / "dados"

st.set_page_config(page_title="Despesas de Teixeira/PB", page_icon="📊", layout="wide")

PLOTLY_LAYOUT = dict(
    paper_bgcolor=SURFACE,
    plot_bgcolor=SURFACE,
    font=dict(color=INK_SECONDARY, family="sans-serif", size=13),
    title_font=dict(color=INK, size=15),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(l=10, r=10, t=50, b=10),
    hoverlabel=dict(bgcolor=SURFACE, font_color=INK),
)
AXIS_STYLE = dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=INK_MUTED), zeroline=False, automargin=True)


def aplicar_tema(fig: go.Figure) -> go.Figure:
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_xaxes(**AXIS_STYLE)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


@st.cache_data
def carregar_metadata() -> dict:
    caminho = DADOS_DIR / "metadata.json"
    if not caminho.exists():
        return {"last_updated": None, "rows": {}}
    return json.loads(caminho.read_text(encoding="utf-8"))


@st.cache_data
def carregar_dados(_last_updated: str | None):
    despesas = pd.read_parquet(DADOS_DIR / "despesas.parquet")
    licitacoes = pd.read_parquet(DADOS_DIR / "licitacoes.parquet")
    return despesas, licitacoes


metadata = carregar_metadata()
despesas, licitacoes = carregar_dados(metadata.get("last_updated"))

st.title("Despesas da Prefeitura de Teixeira/PB")
if metadata.get("last_updated"):
    st.caption(f"Dados atualizados em {metadata['last_updated']} (fonte: TCE-PB / SAGRES, dados abertos)")
else:
    st.caption("Dados ainda não sincronizados — rode `python pipeline/fetch.py && python pipeline/transform.py`.")

# --- filtros ---
st.sidebar.header("Filtros")
anos_disp = sorted(despesas["ano"].dropna().unique().astype(int), reverse=True)
anos_sel = st.sidebar.multiselect("Ano", anos_disp, default=anos_disp[:3] if len(anos_disp) >= 3 else anos_disp)
funcoes_disp = sorted(despesas["funcao"].dropna().unique())
funcoes_sel = st.sidebar.multiselect("Função", funcoes_disp, default=[])
fornecedores_disp = sorted(despesas["nome_credor"].dropna().unique())
fornecedores_sel = st.sidebar.multiselect("Fornecedor", fornecedores_disp, default=[])

df = despesas.copy()
if anos_sel:
    df = df[df["ano"].isin(anos_sel)]
if funcoes_sel:
    df = df[df["funcao"].isin(funcoes_sel)]
if fornecedores_sel:
    df = df[df["nome_credor"].isin(fornecedores_sel)]

if df.empty:
    st.warning("Nenhum registro para os filtros selecionados.")
    st.stop()

# --- KPIs ---
total_empenhado = df["valor_empenhado"].sum()
total_liquidado = df["valor_liquidado"].sum()
total_pago = df["valor_pago"].sum()
execucao = (total_pago / total_empenhado * 100) if total_empenhado else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Empenhado", fmt_reais(total_empenhado))
c2.metric("Liquidado", fmt_reais(total_liquidado))
c3.metric("Pago", fmt_reais(total_pago))
c4.metric("Execução (pago/empenhado)", f"{execucao:.1f}%")

st.divider()

# --- 1. Evolução anual: Empenhado x Liquidado x Pago ---
st.subheader("Evolução anual do gasto")
evolucao = df.groupby("ano", as_index=False)[["valor_empenhado", "valor_liquidado", "valor_pago"]].sum()
evolucao = evolucao.rename(columns={"valor_empenhado": "Empenhado", "valor_liquidado": "Liquidado", "valor_pago": "Pago"})
evolucao_long = evolucao.melt(id_vars="ano", var_name="Estágio", value_name="Valor")
MAPA_ESTAGIO = {"Empenhado": CAT_PALETTE["blue"], "Liquidado": CAT_PALETTE["aqua"], "Pago": CAT_PALETTE["green"]}
fig1 = px.line(
    evolucao_long, x="ano", y="Valor", color="Estágio",
    color_discrete_map=MAPA_ESTAGIO, markers=True,
)
fig1.update_traces(line_width=2, marker_size=8)
fig1.update_yaxes(tickformat="~s", title="R$")
fig1.update_xaxes(title="Ano", dtick=1)
st.plotly_chart(aplicar_tema(fig1), use_container_width=True, theme=None)

# --- 2. Sazonalidade mensal ---
st.subheader("Sazonalidade: em que meses o gasto se concentra")
sazonal = df.groupby("mes_num", as_index=False)["valor_pago"].sum().sort_values("mes_num")
fig2 = px.bar(sazonal, x="mes_num", y="valor_pago", color_discrete_sequence=[CAT_PALETTE["blue"]])
fig2.update_traces(marker_line_width=0)
fig2.update_yaxes(tickformat="~s", title="R$ pago")
fig2.update_xaxes(title="Mês", dtick=1)
fig2.update_layout(showlegend=False)
st.plotly_chart(aplicar_tema(fig2), use_container_width=True, theme=None)

# --- 3. Composição por função de governo ---
st.subheader("Para onde vai o dinheiro: funções de governo")
top_funcoes = df.groupby("funcao", as_index=False)["valor_pago"].sum().sort_values("valor_pago", ascending=True).tail(10)
fig3 = px.bar(top_funcoes, x="valor_pago", y="funcao", orientation="h", color_discrete_sequence=[CAT_PALETTE["blue"]])
fig3.update_traces(marker_line_width=0)
fig3.update_xaxes(tickformat="~s", title="R$ pago")
fig3.update_yaxes(title="")
fig3.update_layout(showlegend=False)
st.plotly_chart(aplicar_tema(fig3), use_container_width=True, theme=None)

# --- 4. Despesas correntes x capital ---
st.subheader("Despesas correntes × capital")
cat_map = {"Despesa Corrente": "Despesas Correntes", "Despesa de Capital": "Despesas de Capital"}
cc = df[df["categoria_economica"].isin(cat_map.keys())].copy()
cc["categoria_economica"] = cc["categoria_economica"].map(cat_map)
pivot_cc = cc.groupby(["ano", "categoria_economica"], as_index=False)["valor_pago"].sum()
MAPA_CC = {"Despesas Correntes": CAT_PALETTE["blue"], "Despesas de Capital": CAT_PALETTE["orange"]}
fig4 = px.bar(
    pivot_cc, x="ano", y="valor_pago", color="categoria_economica",
    color_discrete_map=MAPA_CC, barmode="stack",
)
fig4.update_traces(marker_line_width=0)
fig4.update_yaxes(tickformat="~s", title="R$ pago")
fig4.update_xaxes(title="Ano", dtick=1)
fig4.update_layout(legend_title_text="")
st.plotly_chart(aplicar_tema(fig4), use_container_width=True, theme=None)

# --- 5. Concentração de fornecedores (curva de Lorenz) ---
st.subheader("Concentração de fornecedores")
forn = df.groupby("nome_credor", as_index=False)["valor_pago"].sum().sort_values("valor_pago", ascending=False)
forn = forn[forn["valor_pago"] > 0].reset_index(drop=True)
if len(forn) > 0:
    forn["pct_fornecedores"] = (forn.index + 1) / len(forn) * 100
    forn["pct_acumulado_valor"] = forn["valor_pago"].cumsum() / forn["valor_pago"].sum() * 100
    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(
        x=forn["pct_fornecedores"], y=forn["pct_acumulado_valor"],
        mode="lines", line=dict(color=CAT_PALETTE["violet"], width=2), name="Concentração observada",
        fill="tozeroy", fillcolor=hex_to_rgba(CAT_PALETTE["violet"], 0.13),
    ))
    fig5.add_trace(go.Scatter(
        x=[0, 100], y=[0, 100], mode="lines",
        line=dict(color=INK_MUTED, width=1, dash="dash"), name="Distribuição igualitária",
    ))
    fig5.update_xaxes(title="% dos fornecedores (do maior para o menor)")
    fig5.update_yaxes(title="% acumulado do valor pago")
    st.plotly_chart(aplicar_tema(fig5), use_container_width=True, theme=None)
    top10_pct = forn.head(max(1, len(forn) // 10))["valor_pago"].sum() / forn["valor_pago"].sum() * 100
    st.caption(f"Os 10% de fornecedores que mais recebem concentram {top10_pct:.0f}% do valor pago no período filtrado.")

# --- 6. Execução orçamentária por função (status) ---
st.subheader("Execução orçamentária por função")
exec_funcao = df.groupby("funcao", as_index=False).agg(
    valor_empenhado=("valor_empenhado", "sum"), valor_pago=("valor_pago", "sum")
)
exec_funcao = exec_funcao[exec_funcao["valor_empenhado"] > 0]
exec_funcao["execucao_pct"] = exec_funcao["valor_pago"] / exec_funcao["valor_empenhado"] * 100
exec_funcao = exec_funcao.sort_values("execucao_pct", ascending=True).tail(15)


def status_de(pct: float) -> str:
    if pct >= 90:
        return "good"
    if pct >= 70:
        return "warning"
    return "critical"


exec_funcao["status"] = exec_funcao["execucao_pct"].apply(status_de)
LABEL_STATUS = {"good": "≥ 90% executado", "warning": "70–90% executado", "critical": "< 70% executado"}
fig6 = go.Figure()
for status_key, cor in [("good", STATUS["good"]), ("warning", STATUS["warning"]), ("critical", STATUS["critical"])]:
    sub = exec_funcao[exec_funcao["status"] == status_key]
    fig6.add_trace(go.Bar(
        x=sub["execucao_pct"], y=sub["funcao"], orientation="h",
        marker_color=cor, name=LABEL_STATUS[status_key],
    ))
fig6.update_xaxes(title="% pago do empenhado")
fig6.update_yaxes(title="")
fig6.update_layout(legend_title_text="", barmode="overlay")
st.plotly_chart(aplicar_tema(fig6), use_container_width=True, theme=None)

# --- 7. Despesas sem processo licitatório ---
st.subheader("Despesas sem processo licitatório, por ano")
sem_lic = df.groupby("ano", as_index=False).agg(
    total=("valor_empenhado", "sum"),
    sem_licitacao=("valor_empenhado", lambda s: s[df.loc[s.index, "sem_licitacao"]].sum()),
)
sem_lic["pct_sem_licitacao"] = sem_lic["sem_licitacao"] / sem_lic["total"] * 100
fig7 = px.bar(sem_lic, x="ano", y="pct_sem_licitacao", color_discrete_sequence=[STATUS["serious"]])
fig7.update_traces(marker_line_width=0)
fig7.update_yaxes(title="% do valor empenhado sem licitação")
fig7.update_xaxes(title="Ano", dtick=1)
fig7.update_layout(showlegend=False)
st.plotly_chart(aplicar_tema(fig7), use_container_width=True, theme=None)

st.divider()
st.caption(
    "Fonte: Portal de Dados Abertos do TCE-PB (dados-abertos.tce.pb.gov.br), município de Teixeira/PB (código 215). "
    "Este painel identifica sinais estatísticos, não provas de irregularidade — cruzar com processos administrativos "
    "antes de qualquer conclusão."
)
