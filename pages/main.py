# =================== Clone Edição Platinum (Streamlit + BigQuery) ===================

import os
import pandas as pd
import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit_echarts import st_echarts  # JSON puro

# --------- GUARD: bloqueia acesso direto sem login ---------
if not st.session_state.get("logged_in", False):
    # tenta redirecionar pelo servidor
    try:
        st.switch_page("app.py")
    except Exception:
        pass
    # garante redirecionamento pelo navegador
    st.markdown("<meta http-equiv='refresh' content='0; url=/' />", unsafe_allow_html=True)
    st.stop()
# -----------------------------------------------------------

PROJECT_ID   = "leads-ts"
DATASET      = "Clone"
TABLE_METAS  = f"`{PROJECT_ID}.{DATASET}.MetasClone`"
TABLE_PLAT   = f"`{PROJECT_ID}.{DATASET}.clone_platinum_s`"

# Limites/meta
META_MAX     = 10_000_000.0
BASE_INICIAL = 5_835_589.90
BQ_TZ        = "America/Sao_Paulo"

# ===== Título com ícone =====
st.set_page_config(page_title="Clone Edição Platinum", layout="wide")
st.title("📊 Clone Edição Platinum")

# ---------- Estado p/ refresh ----------
if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = 0
if "last_updated" not in st.session_state:
    st.session_state.last_updated = None

hdr_l, hdr_r = st.columns([1, 1], gap="large")
with hdr_l:
    if st.button("🔄 Atualizar dados", use_container_width=True, type="primary"):
        st.cache_data.clear()               # limpa cache
        st.session_state.refresh_token += 1 # força reconsulta
with hdr_r:
    if st.session_state.last_updated:
        st.info(f"Última atualização: {st.session_state.last_updated}", icon="🕒")

# ---------- Auth ----------
auth_mode = "desconhecido"
try:
    if "gcp_service_account" in st.secrets:
        PROJECT_ID = st.secrets.get("gcp_project_id", PROJECT_ID)
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        bq = bigquery.Client(project=PROJECT_ID, credentials=creds)
        auth_mode = "secrets"
    else:
        SA_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", r"C:\path\to\service_account.json")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SA_PATH
        bq = bigquery.Client(project=PROJECT_ID)
        auth_mode = "arquivo local"
except Exception as e:
    st.error("Falha ao autenticar no BigQuery.")
    st.exception(e)
    st.stop()

# ---------- Cache de consulta ----------
@st.cache_data(show_spinner=False)
def q(sql: str, _bust: int) -> pd.DataFrame:
    return bq.query(sql).result().to_dataframe(create_bqstorage_client=False)

# ---------- Consultas ----------
sql_metas = f"""
SELECT data_meta, Meta_Diaria, Meta_Acumulada
FROM {TABLE_METAS}
ORDER BY data_meta
"""
sql_dep = f"""
SELECT
  data_deposito AS dt_local,
  COUNT(*)      AS qtd_dep,
  SUM(deposito) AS total_deposito
FROM {TABLE_PLAT}
WHERE data_deposito IS NOT NULL
GROUP BY dt_local
ORDER BY dt_local
"""

with st.spinner("Consultando BigQuery…"):
    df_metas = q(sql_metas, st.session_state.refresh_token)
    df_dep   = q(sql_dep,   st.session_state.refresh_token)

st.session_state.last_updated = pd.Timestamp.now(tz=BQ_TZ).strftime("%d/%m/%Y %H:%M:%S")

if df_metas.empty:
    st.warning("Tabela MetasClone vazia.")
    st.stop()

# ---------- Início fixo da série ----------
START_DT = pd.Timestamp(2025, 9, 22)

# ---------- Helpers fmt ----------
def fmt_br(v: float) -> str:
    s = f"{float(v):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_int_br(v: int) -> str:
    return f"{int(v):,}".replace(",", ".")

def fmt_pct(v: float) -> str:
    return f"{v:.2f}%"

def fmt_short(v: float) -> str:
    v = float(v or 0)
    if v >= 1_000_000_000: return f"{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:     return f"{v/1_000_000:.2f}M"
    if v >= 1_000:         return f"{v/1_000:.2f}K"
    return f"{v:.0f}"

# ---------- Séries base ----------
m = df_metas.copy()
m["data_meta"] = pd.to_datetime(m["data_meta"], errors="coerce")
m["Meta_Acumulada"] = pd.to_numeric(m["Meta_Acumulada"], errors="coerce")
m["Meta_Diaria"]    = pd.to_numeric(m["Meta_Diaria"], errors="coerce")
m = m.dropna(subset=["data_meta"]).sort_values("data_meta")
m_ge = m[m["data_meta"] >= START_DT].copy()
m_ge["meta_acum"] = m_ge["Meta_Acumulada"]

if not df_dep.empty:
    d_all = df_dep.copy()
    d_all["dt_local"] = pd.to_datetime(d_all["dt_local"], errors="coerce")
    d_all = d_all.dropna(subset=["dt_local"]).sort_values("dt_local")
else:
    d_all = pd.DataFrame(columns=["dt_local", "qtd_dep", "total_deposito"])

pre_sum_val = float(d_all.loc[d_all["dt_local"] < START_DT, "total_deposito"].sum())
pre_count   = int(d_all.loc[d_all["dt_local"] < START_DT, "qtd_dep"].sum())

d_daily = (
    d_all.loc[d_all["dt_local"] >= START_DT]
         .groupby("dt_local", as_index=False)
         .agg(qtd_dep=("qtd_dep", "sum"), total_deposito=("total_deposito", "sum"))
    if not d_all.empty else pd.DataFrame(columns=["dt_local", "qtd_dep", "total_deposito"])
)

max_m = m_ge["data_meta"].max() if not m_ge.empty else START_DT
max_d = d_all["dt_local"].max()  if not d_all.empty else START_DT
dmax  = max(max_m, max_d)
cal   = pd.DataFrame({"date": pd.date_range(START_DT, dmax, freq="D")})

serie_meta = cal.merge(m_ge[["data_meta", "meta_acum"]],
                       left_on="date", right_on="data_meta", how="left").drop(columns=["data_meta"])
serie_meta["meta_acum"] = serie_meta["meta_acum"].ffill()

serie_dep = cal.merge(d_daily.rename(columns={"dt_local": "date"}), on="date", how="left").fillna({"qtd_dep": 0, "total_deposito": 0.0})
serie_dep["total_deposito"] = pd.to_numeric(serie_dep["total_deposito"], errors="coerce").fillna(0.0)
serie_dep["qtd_dep"]        = pd.to_numeric(serie_dep["qtd_dep"], errors="coerce").fillna(0).astype(int)
start_realizado = BASE_INICIAL + pre_sum_val
serie_dep["realizado_acum"] = start_realizado + serie_dep["total_deposito"].cumsum()

# ---------- KPIs ----------
valor_depositos_total = pre_sum_val + float(serie_dep["total_deposito"].sum())
qtd_depositos_total   = pre_count   + int(serie_dep["qtd_dep"].sum())
realizado_atual       = float(serie_dep["realizado_acum"].iloc[-1]) if not serie_dep.empty else start_realizado
meta_atual            = float(serie_meta["meta_acum"].iloc[-1])     if not serie_meta.empty else 0.0

den = (META_MAX - BASE_INICIAL)
pct_meta = ((realizado_atual - BASE_INICIAL) / den) * 100.0 if den > 0 else 0.0
pct_meta = max(0.0, min(100.0, pct_meta))

# ---------- Estilo + espaçamento (apenas nos 3 cards da esquerda) ----------
st.markdown("""
<style>
.kpi-card{
  background:#0f172a;border:1px solid #1f2937;box-shadow:0 1px 12px rgba(0,0,0,.25);
  border-radius:14px;padding:16px 18px;
}
.kpi-header{display:flex;align-items:center;gap:10px;color:#A7B0C0;font-size:1.06rem;font-weight:700;margin-bottom:10px}
.kpi-icon{width:30px;height:30px;border-radius:999px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.06);border:1px solid #1f2937;font-size:18px}
.kpi-value{font-size:1.9rem;font-weight:900;color:#E5E7EB;line-height:1.08}
.kpi-sub{display:none}

/* container dos 3 cards */
.col-left-stack { display:flex; flex-direction:column; }
/* espaçamento suave entre os cards sem afetar o último */
.col-left-stack > .kpi-card { margin-bottom: 14px; }
.col-left-stack > .kpi-card:last-child { margin-bottom: 0; }

/* direita mantém seu espaçamento normal */
.col-right-stack{ display:flex; flex-direction:column; gap:20px; }

.meta-info{margin-top:8px;color:#E5E7EB;font-size:1rem}
.meta-info .muted{color:#9CA3AF}
.footer-auth{ margin-top:28px;padding:10px 12px;border-top:1px solid #1f2937;color:#9CA3AF;font-size:.95rem; }
.block-container div:empty { display:none !important; }
</style>
""", unsafe_allow_html=True)

# ========== LAYOUT PRINCIPAL – 2 colunas ==========
left_col, right_col = st.columns([1, 1], gap="large")

# ----- ESQUERDA: 3 cards -----
with left_col:
    st.markdown('<div class="col-left-stack">', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-header"><div class="kpi-icon">📦</div> Quantidade de depósitos</div>
      <div class="kpi-value">{fmt_int_br(qtd_depositos_total)}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-header"><div class="kpi-icon">💵</div> Valor de depósitos</div>
      <div class="kpi-value">${fmt_br(valor_depositos_total)}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-header"><div class="kpi-icon">🎯</div> Porcentagem da meta</div>
      <div class="kpi-value">{fmt_pct(pct_meta)}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ----- DIREITA: Barra da Meta + “Depósitos de hoje” -----
with right_col:
    now_sp     = pd.Timestamp.now(tz=BQ_TZ)
    today_date = pd.Timestamp(now_sp.date())

    metas_today = m[m["data_meta"] == today_date]["Meta_Diaria"]
    if not metas_today.empty and pd.notna(metas_today.iloc[0]):
        meta_diaria_hoje = float(metas_today.iloc[0])
    else:
        last_meta_diaria = m["Meta_Diaria"].dropna()
        meta_diaria_hoje = float(last_meta_diaria.iloc[-1]) if not last_meta_diaria.empty else 10_000.0

    dep_today = d_all.loc[d_all["dt_local"] == today_date, "total_deposito"]
    depositos_hoje = float(dep_today.iloc[0]) if not dep_today.empty else 0.0
    pct_hoje = (depositos_hoje / meta_diaria_hoje * 100.0) if meta_diaria_hoje > 0 else 0.0
    pct_hoje = max(0.0, min(100.0, pct_hoje))

    st.markdown('<div class="col-right-stack">', unsafe_allow_html=True)

    st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-header"><div class="kpi-icon">🧭</div> Meta Diária</div>', unsafe_allow_html=True)

    bar_opts = {
        "backgroundColor": "transparent",
        "grid": {"left": 10, "right": 10, "top": 8, "bottom": 0, "containLabel": False},
        "xAxis": {"type": "value", "min": 0, "max": float(meta_diaria_hoje),
                  "axisLine": {"show": False}, "axisTick": {"show": False},
                  "axisLabel": {"show": False}, "splitLine": {"show": False}},
        "yAxis": {"type": "category", "data": [""],
                  "axisLine": {"show": False}, "axisTick": {"show": False},
                  "axisLabel": {"show": False}},
        "series": [
            {"type": "bar","data": [float(meta_diaria_hoje)],"barWidth": 26,
             "itemStyle": {"color": "rgba(255,255,255,0.10)", "borderRadius": [13,13,13,13]},
             "silent": True, "z": 1, "barGap": "-100%"},
            {"type": "bar","data": [min(float(depositos_hoje), float(meta_diaria_hoje))],"barWidth": 26,
             "itemStyle": {"color": "#000064", "borderRadius": [13,13,13,13]},
             "label": {"show": False}, "z": 2},
        ],
        "animation": True,
    }
    st_echarts(options=bar_opts, height="54px", theme="dark")

    # Com cifrão nos dois valores:
    st.markdown(
        f'<div class="meta-info">$ {fmt_br(depositos_hoje)} de  $ {fmt_br(meta_diaria_hoje)} • Progresso: {pct_hoje:.2f}%.</div>',
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-header"><div class="kpi-icon">💰</div> Depósitos de hoje</div>
      <div class="kpi-value">${fmt_br(depositos_hoje)}</div>
      <div class="kpi-sub" style="display:block;">Data: {today_date:%d/%m/%Y}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ---------- GRÁFICO ----------
st.markdown("---")

x_labels = cal["date"].dt.strftime("%d/%m").tolist()
y_barras = serie_dep["realizado_acum"].round(2).where(pd.notna, None).tolist()
y_linha  = serie_meta["meta_acum"].round(2).where(pd.notna, None).tolist()

SUBMETA_LABEL = next((d.strftime("%d/%m") for d in cal["date"] if d.month == 11 and d.day == 15), "15/11")
SUBMETA_VALOR = 9_000_000.0

def _safe_max(seq, fallback):
    seq = [v for v in seq if v is not None]
    return max(seq) if seq else fallback

y_max = max(_safe_max(y_barras, start_realizado), _safe_max(y_linha, start_realizado))
y_min = max(0.0, start_realizado - 0.02 * (y_max - start_realizado))

# Rótulos dentro das colunas
bar_data_with_labels = []
for v in y_barras:
    if v is None:
        bar_data_with_labels.append(None); continue
    bar_data_with_labels.append({
        "value": float(v),
        "label": {
            "show": True,
            "position": "insideTop",
            "distance": 6,
            "formatter": fmt_short(float(v)),
            "color": "#E5E7EB",
            "fontSize": 10
        }
    })

n = len(y_barras)
WINDOW = min(25, max(1, n))
start_idx, end_idx = 0, WINDOW - 1

options = {
    "backgroundColor": "transparent",
    "title": {"text": "Forecast: Realizado vs Meta","left": 0,"top": 8,"textStyle": {"color": "#E5E7EB","fontSize": 18}},
    "tooltip": {"trigger": "axis"},
    "legend": {"data": ["Realizado","Meta"], "top": 36, "textStyle": {"color": "#E5E7EB"}},
    "grid": {"left": 64, "right": 20, "top": 72, "bottom": 80, "containLabel": True},
    "xAxis": {"type": "category", "data": x_labels, "axisLabel": {"color": "#E5E7EB", "interval": 0}},
    "yAxis": {"type": "value","min": float(y_min),"max": "dataMax",
              "axisLabel": {"show": False},"axisLine": {"show": False},
              "axisTick": {"show": False},"splitLine": {"show": True}},
    "dataZoom": [
        {"type": "slider","xAxisIndex": 0,"startValue": start_idx,"endValue": end_idx,"zoomLock": True,
         "minValueSpan": WINDOW,"maxValueSpan": WINDOW,"bottom": 28,"height": 24,"handleSize": 0,
         "handleStyle": {"opacity": 0},"showDetail": False,"brushSelect": False,
         "fillerColor": "rgba(255,255,255,0.18)","backgroundColor": "rgba(255,255,255,0.06)",
         "borderColor": "rgba(255,255,255,0.15)"},
        {"type": "inside","xAxisIndex": 0,"startValue": start_idx,"endValue": end_idx,
         "zoomLock": True,"minValueSpan": WINDOW,"maxValueSpan": WINDOW}
    ],
    "series": [
        {
            "name": "Realizado",
            "type": "bar",
            "data": bar_data_with_labels,
            "barMaxWidth": 53,
            "itemStyle": {"borderRadius": [8, 8, 0, 0], "color": "#000064"},
            "label": {"show": True},
            "labelLayout": {"hideOverlap": True}
        },
        {
            "name": "Meta",
            "type": "line",
            "data": y_linha,
            "symbol": "circle",
            "itemStyle": {"color": "#34d399"},
            "lineStyle": {"width": 3, "type": "dashed", "color": "#34d399"},
            "markLine": {
                "symbol": "none",
                "lineStyle": {"type": "dotted", "color": "#9CA3AF"},
                "label": {"color": "#E5E7EB", "fontSize": 12},
                "data": [
                    {"xAxis": SUBMETA_LABEL, "name": "15/11"},
                    {"yAxis": SUBMETA_VALOR, "name": "9M"},
                ],
            },
            "markPoint": {
                "symbolSize": 48,
                "label": {"color": "#0f172a", "fontWeight": "700"},
                "itemStyle": {"color": "#34d399"},
                "data": [{"coord": [SUBMETA_LABEL, SUBMETA_VALOR], "value": "9M"}],
            },
        }
    ]
}
st_echarts(options=options, height="520px", theme="dark")

# ===== Rodapé com modo de autenticação =====
st.markdown(f"""
<div class="footer-auth">🔐 Modo de autenticação: <strong>{auth_mode}</strong></div>
""", unsafe_allow_html=True)
