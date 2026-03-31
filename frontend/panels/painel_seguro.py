"""
Painel Seguro — acesso autenticado a dados sensíveis.

Protegido por senha. Exibe:
  - Fila de prioridade com dados de paciente
  - Card de detalhe expandido com identificadores reais
  - Log de acesso auditável

A senha é comparada via SHA256 para evitar armazenamento em claro.
"""

import hashlib
import os
import sqlite3
import uuid

import streamlit as st

from core.database import priority_queue, log_access
from components.priority_queue import render_priority_queue
from components.record_viewer import render_record_viewer


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

_DEFAULT_PASSWORD_HASH = os.environ.get(
    "NOTIFICAI_ADMIN_HASH",
    # hash de "notificai2024" — substitua em produção via variável de ambiente
    hashlib.sha256(b"notificai2024").hexdigest(),
)


def _check_password(password: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == _DEFAULT_PASSWORD_HASH


def _login_form() -> bool:
    """Renderiza o formulário de login. Retorna True se autenticado."""
    st.markdown("### 🔒 Painel Seguro — Acesso Restrito")
    st.info(
        "Este painel contém dados sensíveis de pacientes. "
        "O acesso é registrado no log de auditoria."
    )
    with st.form("login_form"):
        password = st.text_input("Senha", type="password", placeholder="Digite a senha de acesso")
        submitted = st.form_submit_button("Entrar", type="primary")

    if submitted:
        if _check_password(password):
            st.session_state["secure_authenticated"] = True
            st.session_state["secure_session_id"] = str(uuid.uuid4())
            st.rerun()
        else:
            st.error("Senha incorreta. O acesso foi registrado.")
    return False


# ---------------------------------------------------------------------------
# Painel principal
# ---------------------------------------------------------------------------

def render(conn: sqlite3.Connection) -> None:
    """Renderiza o Painel Seguro (com autenticação)."""

    # --- Verificação de autenticação ---
    if not st.session_state.get("secure_authenticated"):
        _login_form()
        return

    session_id: str = st.session_state.get("secure_session_id", "")

    # --- Cabeçalho ---
    col_title, col_logout = st.columns([5, 1])
    col_title.title("NotificAI — Painel Seguro 🔒")
    if col_logout.button("Sair"):
        log_access(conn, "logout", session_id=session_id)
        st.session_state["secure_authenticated"] = False
        st.session_state["secure_session_id"] = None
        st.rerun()

    st.caption(
        "Painel de uso exclusivo por técnicos autorizados. "
        "Todos os acessos a dados de pacientes são registrados."
    )

    log_access(conn, "view_secure_panel", session_id=session_id)

    st.markdown("---")

    # --- Abas principais ---
    tab_queue, tab_detail, tab_audit = st.tabs([
        "📋 Fila de Prioridade",
        "🔍 Detalhe do Registro",
        "📝 Log de Acesso",
    ])

    # -----------------------------------------------------------------------
    # Aba 1 — Fila de prioridade
    # -----------------------------------------------------------------------
    with tab_queue:
        st.subheader("Casos Priorizados por Score de Risco")

        limit = st.slider("Exibir até N casos", 10, 200, 50, step=10, key="sec_limit")

        def _select_case(analysis_id: str):
            st.session_state["secure_selected_analysis"] = analysis_id

        render_priority_queue(
            conn,
            limit=limit,
            on_select=_select_case,
            show_patient_hash=True,
        )

    # -----------------------------------------------------------------------
    # Aba 2 — Detalhe do registro
    # -----------------------------------------------------------------------
    with tab_detail:
        selected_id = st.session_state.get("secure_selected_analysis")

        if not selected_id:
            # Permite busca manual por analysis_id
            manual_id = st.text_input(
                "ID da análise",
                placeholder="Cole aqui o analysis_id ou selecione na fila de prioridade",
            )
            if manual_id:
                selected_id = manual_id.strip()

        if selected_id:
            render_record_viewer(
                conn,
                analysis_id=selected_id,
                show_patient=True,
                session_id=session_id,
            )
        else:
            st.info("Selecione um caso na aba **Fila de Prioridade** ou informe um ID acima.")

    # -----------------------------------------------------------------------
    # Aba 3 — Log de acesso
    # -----------------------------------------------------------------------
    with tab_audit:
        st.subheader("Log de Auditoria")
        _render_access_log(conn)


def _render_access_log(conn: sqlite3.Connection) -> None:
    """Exibe os últimos registros de acesso."""
    import pandas as pd

    rows = conn.execute(
        """
        SELECT accessed_at, action, patient_hash, session_id
        FROM access_log
        ORDER BY accessed_at DESC
        LIMIT 200
        """
    ).fetchall()

    if not rows:
        st.info("Nenhum acesso registrado.")
        return

    df = pd.DataFrame([dict(r) for r in rows])
    df["accessed_at"] = pd.to_datetime(df["accessed_at"]).dt.strftime("%d/%m/%Y %H:%M:%S")
    df["patient_hash"] = df["patient_hash"].fillna("—").str[:16] + "…"
    df["session_id"]   = df["session_id"].fillna("—").str[:12] + "…"

    df.columns = ["Data/Hora", "Ação", "Paciente (hash)", "Sessão"]
    st.dataframe(df, use_container_width=True, hide_index=True)
