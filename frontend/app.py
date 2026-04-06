"""
NotificAI — Ponto de entrada da aplicação Streamlit.

Execução:
    streamlit run frontend/app.py

Estrutura de navegação (sidebar):
    ├── 📊 Painel Público    — estatísticas anônimas, upload, monitoramento
    └── 🔒 Painel Seguro    — dados sensíveis, fila de prioridade (autenticado)
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
# CSS global mínimo
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Cabeçalho compacto */
    header[data-testid="stHeader"] { background: #1a252f; }

    /* Sidebar */
    section[data-testid="stSidebar"] { background: #1e2c3a; color: white; }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] label { color: #ecf0f1 !important; }

    /* Métricas */
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; }

    /* Linhas divisórias */
    hr { border-color: #ecf0f1; }
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

with st.sidebar:
    st.markdown(
        "<div style='font-size:2.2rem;text-align:center'>🏥</div>",
        unsafe_allow_html=True,
    )
    st.markdown("## NotificAI")
    st.caption("Sistema de Apoio à Notificação de Violências")
    st.markdown("---")

    page = st.radio(
        "Navegar para",
        options=["📊 Painel Público", "🔒 Painel Seguro"],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Indicador de status do monitoramento de pasta
    watcher = st.session_state.get("folder_watcher")
    if watcher and watcher.is_alive():
        folder_path = st.session_state.get("monitor_folder_path", "")
        st.success(f"🟢 Monitorando\n`{folder_path}`")
    else:
        st.info("⚪ Monitoramento inativo")

    st.markdown("---")
    st.caption("v2.0 · 2025 · NUVE")

# ---------------------------------------------------------------------------
# Roteamento de página
# ---------------------------------------------------------------------------

# Recarrega métricas se documentos foram atualizados
if st.session_state.pop("docs_updated", False):
    st.cache_resource.clear()
    conn = _get_conn()

if page == "📊 Painel Público":
    from panels.painel_publico import render
    render(conn)
else:
    from panels.painel_seguro import render
    render(conn)
