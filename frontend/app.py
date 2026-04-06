"""
NotificAI — Ponto de entrada da aplicação Streamlit.

Execução:
    streamlit run frontend/app.py
"""

import sys
from pathlib import Path

_FRONTEND = Path(__file__).parent
_ROOT     = _FRONTEND.parent
sys.path.insert(0, str(_FRONTEND))
sys.path.insert(0, str(_ROOT))

import streamlit as st
from core.database import get_connection

st.set_page_config(
    page_title="NotificAI · NUVE",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Design System — CSS global
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Reset & base ─────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.stApp {
    background: #0B0F19 !important;
}
.block-container {
    padding: 1rem 1.5rem 2rem !important;
    max-width: 100% !important;
}

/* ── Scrollbar ────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0B0F19; }
::-webkit-scrollbar-thumb { background: #2D3748; border-radius: 3px; }

/* ── Header ───────────────────────────────────────────────────────────── */
header[data-testid="stHeader"] {
    background: linear-gradient(90deg, #0B0F19 0%, #111827 100%) !important;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    height: 3rem !important;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: #0F1623 !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
section[data-testid="stSidebar"] > div { padding: 1.2rem 1rem !important; }
section[data-testid="stSidebar"] .stMarkdown p { color: #94A3B8 !important; font-size: 0.82rem; }
section[data-testid="stSidebar"] label { color: #CBD5E1 !important; }

/* ── Radio nav buttons ────────────────────────────────────────────────── */
div[role="radiogroup"] label {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    margin-bottom: 6px !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    color: #94A3B8 !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}
div[role="radiogroup"] label:hover {
    background: rgba(59,130,246,0.12) !important;
    border-color: rgba(59,130,246,0.3) !important;
    color: #E2E8F0 !important;
}
div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child { display: none !important; }

/* ── Métricas ─────────────────────────────────────────────────────────── */
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #F1F5F9 !important;
}
[data-testid="stMetricLabel"] { color: #64748B !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 0.05em; }
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; }
[data-testid="metric-container"] {
    background: #141C2E !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
}

/* ── Botões ───────────────────────────────────────────────────────────── */
div.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    padding: 8px 16px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    transition: all 0.2s !important;
    background: rgba(255,255,255,0.05) !important;
    color: #CBD5E1 !important;
}
div.stButton > button:hover {
    background: rgba(255,255,255,0.1) !important;
    border-color: rgba(255,255,255,0.2) !important;
    color: #F1F5F9 !important;
    transform: translateY(-1px) !important;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #3B82F6, #2563EB) !important;
    border-color: transparent !important;
    color: white !important;
    box-shadow: 0 4px 12px rgba(59,130,246,0.3) !important;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #60A5FA, #3B82F6) !important;
    box-shadow: 0 6px 16px rgba(59,130,246,0.4) !important;
    transform: translateY(-2px) !important;
}

/* ── Tabs ─────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 8px 8px 0 0 !important;
    color: #64748B !important;
    font-size: 0.83rem !important;
    font-weight: 500 !important;
    padding: 8px 18px !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #94A3B8 !important; background: rgba(255,255,255,0.04) !important; }
.stTabs [aria-selected="true"] {
    color: #60A5FA !important;
    border-bottom: 2px solid #3B82F6 !important;
    background: rgba(59,130,246,0.08) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 16px 0 !important; }

/* ── Inputs ───────────────────────────────────────────────────────────── */
input, textarea, select,
div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea {
    background: #141C2E !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
    font-family: 'Inter', sans-serif !important;
}
input:focus, textarea:focus {
    border-color: #3B82F6 !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}

/* ── Selectbox ────────────────────────────────────────────────────────── */
div[data-baseweb="select"] > div {
    background: #141C2E !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
}

/* ── Expander ─────────────────────────────────────────────────────────── */
details {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
summary {
    color: #94A3B8 !important;
    font-size: 0.85rem !important;
    padding: 10px 14px !important;
}

/* ── Alertas ──────────────────────────────────────────────────────────── */
div[data-testid="stAlert"] {
    border-radius: 10px !important;
    border-left-width: 4px !important;
    font-size: 0.85rem !important;
}

/* ── Dataframe ────────────────────────────────────────────────────────── */
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    overflow: hidden;
}

/* ── Slider ───────────────────────────────────────────────────────────── */
div[data-testid="stSlider"] > div > div > div { background: #3B82F6 !important; }

/* ── Divisórias ───────────────────────────────────────────────────────── */
hr { border-color: rgba(255,255,255,0.07) !important; margin: 1rem 0 !important; }

/* ── Caption / help text ──────────────────────────────────────────────── */
small, .stCaption, [data-testid="stCaptionContainer"] {
    color: #4B5563 !important;
    font-size: 0.78rem !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Conexão com banco
# ---------------------------------------------------------------------------
@st.cache_resource
def _get_conn():
    return get_connection()

conn = _get_conn()

# ---------------------------------------------------------------------------
# Sidebar — navegação
# ---------------------------------------------------------------------------
_PAGES = {
    "🖥️  Estação de Trabalho": "tecnico",
    "📊  Painel Público":       "publico",
    "🔒  Painel Seguro":        "seguro",
}

with st.sidebar:
    # Logo
    st.markdown("""
    <div style="
        display:flex; align-items:center; gap:10px;
        padding:4px 0 20px;
    ">
        <div style="
            width:38px; height:38px;
            background: linear-gradient(135deg,#3B82F6,#1D4ED8);
            border-radius:10px;
            display:flex; align-items:center; justify-content:center;
            font-size:1.2rem; box-shadow:0 4px 12px rgba(59,130,246,0.35);
        ">🏥</div>
        <div>
            <div style="color:#F1F5F9;font-weight:700;font-size:1rem;line-height:1.1;">NotificAI</div>
            <div style="color:#4B5563;font-size:0.72rem;">NUVE · HC-FMUSP</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='color:#4B5563;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;'>NAVEGAÇÃO</div>", unsafe_allow_html=True)

    page_label = st.radio("nav", options=list(_PAGES.keys()), index=0, label_visibility="collapsed")
    page = _PAGES[page_label]

    st.markdown("<hr style='margin:16px 0;'>", unsafe_allow_html=True)

    # Status do monitoramento
    watcher = st.session_state.get("folder_watcher")
    if watcher and watcher.is_alive():
        folder_path = st.session_state.get("monitor_folder_path", "")
        st.markdown(f"""
        <div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);
            border-radius:8px;padding:8px 12px;font-size:0.78rem;color:#34D399;">
            <span style="display:inline-block;width:6px;height:6px;background:#10B981;
                border-radius:50%;margin-right:6px;"></span>
            Monitorando<br>
            <span style="color:#4B5563;word-break:break-all;">{folder_path}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
            border-radius:8px;padding:8px 12px;font-size:0.78rem;color:#4B5563;">
            <span style="display:inline-block;width:6px;height:6px;background:#374151;
                border-radius:50%;margin-right:6px;"></span>
            Monitoramento inativo
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div style="position:absolute;bottom:20px;left:16px;right:16px;">
        <div style="color:#1F2937;font-size:0.72rem;text-align:center;">v2.0 · 2025</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Roteamento
# ---------------------------------------------------------------------------
if st.session_state.pop("docs_updated", False):
    st.cache_resource.clear()
    conn = _get_conn()

if page == "tecnico":
    from panels.painel_tecnico import render
    render(conn)
elif page == "publico":
    from panels.painel_publico import render
    render(conn)
else:
    from panels.painel_seguro import render
    render(conn)
