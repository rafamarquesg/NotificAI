"""
NotificAI — Ponto de entrada da aplicação Streamlit.

Execução:
    streamlit run frontend/app.py

Estrutura de navegação (sidebar):
    ├── 🖥️ Estação de Trabalho  — revisão de casos, decisão, ficha SINAN (padrão)
    ├── 📊 Painel Público       — estatísticas anônimas, upload, monitoramento
    └── 🔒 Painel Seguro        — fila completa, exportação, auditoria
"""

import sys
from pathlib import Path

# Garante que módulos de frontend e backend sejam encontrados
_FRONTEND = Path(__file__).parent
_ROOT     = _FRONTEND.parent

sys.path.insert(0, str(_FRONTEND))
sys.path.insert(0, str(_ROOT))

import streamlit as st

from core.database import get_connection

# ---------------------------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="NotificAI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS global
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Cabeçalho */
    header[data-testid="stHeader"] { background: #1a252f; }

    /* Sidebar */
    section[data-testid="stSidebar"] { background: #1e2c3a; color: white; }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] label { color: #ecf0f1 !important; }

    /* Métricas */
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }

    /* Botões primários */
    div.stButton > button[kind="primary"] {
        background: #e74c3c;
        border: none;
        font-weight: 600;
    }
    div.stButton > button[kind="primary"]:hover { background: #c0392b; }

    /* Tabs mais compactas */
    .stTabs [data-baseweb="tab"] { padding: 6px 16px; font-size: 0.88rem; }

    /* Linhas divisórias */
    hr { border-color: #2c3e50; }

    /* Remove padding excessivo no topo em wide mode */
    .block-container { padding-top: 1rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Conexão com banco de dados (singleton por sessão)
# ---------------------------------------------------------------------------

@st.cache_resource
def _get_conn():
    return get_connection()

conn = _get_conn()

# ---------------------------------------------------------------------------
# Sidebar — navegação
# ---------------------------------------------------------------------------

_PAGES = {
    "🖥️ Estação de Trabalho": "tecnico",
    "📊 Painel Público":       "publico",
    "🔒 Painel Seguro":        "seguro",
}

with st.sidebar:
    st.markdown(
        "<div style='font-size:2.2rem;text-align:center;margin-bottom:4px;'>🏥</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='text-align:center;color:#ecf0f1;font-size:1.1rem;"
        "font-weight:700;margin-bottom:2px;'>NotificAI</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='text-align:center;color:#7f8c8d;font-size:0.78rem;"
        "margin-bottom:12px;'>Notificação de Violências — NUVE</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    page_label = st.radio(
        "Navegar para",
        options=list(_PAGES.keys()),
        index=0,
        label_visibility="collapsed",
    )
    page = _PAGES[page_label]

    st.markdown("---")

    # Indicador de monitoramento de pasta
    watcher = st.session_state.get("folder_watcher")
    if watcher and watcher.is_alive():
        folder_path = st.session_state.get("monitor_folder_path", "")
        st.success(f"🟢 Monitorando\n`{folder_path}`")
    else:
        st.info("⚪ Monitoramento inativo")

    st.markdown("---")

    # Dica de acesso rápido
    if page != "tecnico":
        st.markdown(
            "<div style='color:#7f8c8d;font-size:0.78rem;'>"
            "💡 Use <strong style='color:#ecf0f1;'>Estação de Trabalho</strong>"
            " para revisar casos e gerar fichas SINAN.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")

    st.caption("v2.0 · 2025 · HC-FMUSP / NUVE")

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
