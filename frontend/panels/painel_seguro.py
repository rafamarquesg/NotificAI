"""
Painel Seguro — acesso autenticado a dados sensíveis.

Protegido por senha. Exibe:
  - Fila de prioridade com workflow de status
  - Card de detalhe expandido com identificadores reais
  - Timeline do paciente com detecção de reincidência
  - Exportação SINAN / Excel
  - Estatísticas de feedback e acurácia
  - Log de acesso auditável
"""

import hashlib
import os
import sqlite3
import uuid
from datetime import date

import streamlit as st

from core.database import log_access, get_feedback_stats
from core.export import export_sinan_csv, export_full_json, export_excel
from components.priority_queue import render_priority_queue
from components.record_viewer import render_record_viewer
from components.timeline_viewer import render_patient_timeline


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

_DEFAULT_PASSWORD_HASH = os.environ.get(
    "NOTIFICAI_ADMIN_HASH",
    hashlib.sha256(b"notificai2024").hexdigest(),
)


def _check_password(password: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == _DEFAULT_PASSWORD_HASH


def _login_form() -> bool:
    st.markdown("### 🔒 Painel Seguro — Acesso Restrito")
    st.info(
        "Este painel contém dados sensíveis de pacientes. "
        "O acesso é registrado no log de auditoria."
    )
    with st.form("login_form"):
        password  = st.text_input("Senha", type="password", placeholder="Digite a senha de acesso")
        submitted = st.form_submit_button("Entrar", type="primary")

    if submitted:
        if _check_password(password):
            st.session_state["secure_authenticated"] = True
            st.session_state["secure_session_id"]    = str(uuid.uuid4())
            st.rerun()
        else:
            st.error("Senha incorreta. O acesso foi registrado.")
    return False


# ---------------------------------------------------------------------------
# Painel principal
# ---------------------------------------------------------------------------

def render(conn: sqlite3.Connection) -> None:
    if not st.session_state.get("secure_authenticated"):
        _login_form()
        return

    session_id: str = st.session_state.get("secure_session_id", "")

    col_title, col_logout = st.columns([5, 1])
    col_title.title("NotificAI — Painel Seguro 🔒")
    if col_logout.button("Sair"):
        log_access(conn, "logout", session_id=session_id)
        st.session_state["secure_authenticated"] = False
        st.session_state["secure_session_id"]    = None
        st.rerun()

    st.caption("Painel de uso exclusivo por técnicos autorizados. Todos os acessos são registrados.")
    log_access(conn, "view_secure_panel", session_id=session_id)
    st.markdown("---")

    # -----------------------------------------------------------------------
    # Abas
    # -----------------------------------------------------------------------
    tab_queue, tab_detail, tab_timeline, tab_export, tab_feedback, tab_audit = st.tabs([
        "📋 Fila de Prioridade",
        "🔍 Detalhe do Registro",
        "⏱️ Timeline do Paciente",
        "📤 Exportar",
        "🎯 Feedback / Acurácia",
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
            show_workflow_controls=True,
        )

    # -----------------------------------------------------------------------
    # Aba 2 — Detalhe do registro
    # -----------------------------------------------------------------------
    with tab_detail:
        selected_id = st.session_state.get("secure_selected_analysis")
        if not selected_id:
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
    # Aba 3 — Timeline do paciente
    # -----------------------------------------------------------------------
    with tab_timeline:
        st.subheader("Timeline do Paciente")
        st.caption("Mostra todos os documentos associados a um mesmo paciente (pseudônimo). Detecta reincidência.")

        ph_input = st.text_input(
            "Hash do paciente",
            placeholder="Cole aqui o patient_hash (da fila ou do detalhe)",
            key="timeline_hash",
        )

        if ph_input:
            log_access(conn, "view_timeline", patient_hash=ph_input, session_id=session_id)
            render_patient_timeline(
                conn,
                patient_hash=ph_input.strip(),
                session_id=session_id,
                on_select_analysis=lambda aid: st.session_state.update(
                    {"secure_selected_analysis": aid}
                ),
            )
        else:
            st.info("Informe o hash do paciente acima para visualizar a timeline.")

    # -----------------------------------------------------------------------
    # Aba 4 — Exportação
    # -----------------------------------------------------------------------
    with tab_export:
        _render_export_tab(conn, session_id)

    # -----------------------------------------------------------------------
    # Aba 5 — Feedback / Acurácia
    # -----------------------------------------------------------------------
    with tab_feedback:
        _render_feedback_tab(conn)

    # -----------------------------------------------------------------------
    # Aba 6 — Log de acesso
    # -----------------------------------------------------------------------
    with tab_audit:
        st.subheader("Log de Auditoria")
        _render_access_log(conn)


# ---------------------------------------------------------------------------
# Sub-renderers das abas
# ---------------------------------------------------------------------------

def _render_export_tab(conn: sqlite3.Connection, session_id: str) -> None:
    st.subheader("Exportar Dados")
    st.caption(
        "Exporte os casos no layout SINAN (CSV), planilha Excel ou JSON completo. "
        "**Nenhum dado de identificação pessoal** é incluído nas exportações."
    )

    all_types = [
        "(todos)", "Violência Física", "Violência Sexual",
        "Violência Psicológica/Moral", "Violência Autoprovocada",
        "Negligência/Abandono", "Trabalho Infantil",
        "Tráfico de Pessoas", "Outros/Não Classificado",
    ]

    with st.form("export_form"):
        ec1, ec2, ec3 = st.columns(3)
        start_date = ec1.date_input("Data inicial", value=None, key="exp_start")
        end_date   = ec2.date_input("Data final",   value=None, key="exp_end")
        ntype      = ec3.selectbox("Tipo de notificação", all_types, key="exp_type")

        ef1, ef2, ef3 = st.columns(3)
        btn_csv  = ef1.form_submit_button("📥 Exportar CSV (SINAN)", type="primary")
        btn_xlsx = ef2.form_submit_button("📊 Exportar Excel")
        btn_json = ef3.form_submit_button("🔗 Exportar JSON")

    start_str = start_date.isoformat() if start_date else None
    end_str   = end_date.isoformat()   if end_date   else None
    type_str  = None if ntype == "(todos)" else ntype

    if btn_csv:
        log_access(conn, "export_csv", session_id=session_id)
        data = export_sinan_csv(conn, start_str, end_str, type_str)
        fname = f"notificai_sinan_{date.today()}.csv"
        st.download_button("⬇️ Baixar CSV", data=data, file_name=fname, mime="text/csv")

    if btn_xlsx:
        log_access(conn, "export_xlsx", session_id=session_id)
        data = export_excel(conn, start_str, end_str)
        if data:
            fname = f"notificai_{date.today()}.xlsx"
            st.download_button(
                "⬇️ Baixar Excel", data=data, file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.warning("Instale `openpyxl` para exportar em Excel: `pip install openpyxl`")

    if btn_json:
        log_access(conn, "export_json", session_id=session_id)
        data = export_full_json(conn, start_str, end_str)
        fname = f"notificai_{date.today()}.json"
        st.download_button("⬇️ Baixar JSON", data=data, file_name=fname, mime="application/json")


def _render_feedback_tab(conn: sqlite3.Connection) -> None:
    st.subheader("Estatísticas de Feedback")
    st.caption(
        "Mostra a acurácia da classificação automática com base nos feedbacks "
        "enviados pelos técnicos. Use esses dados para decidir quando retreinar o modelo."
    )

    stats = get_feedback_stats(conn)
    total   = stats["total"]
    correct = stats["correct"]
    acc     = stats["accuracy"]

    if total == 0:
        st.info(
            "Nenhum feedback registrado ainda. "
            "Use o botão de feedback na aba **Detalhe do Registro** para iniciar."
        )
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Total de feedbacks", total)
    m2.metric("Classificações corretas", correct)
    m3.metric(
        "Acurácia estimada",
        f"{acc:.0%}" if acc is not None else "—",
        delta=f"{acc - 0.8:.0%} vs meta 80%" if acc is not None else None,
        delta_color="normal",
    )

    corrections = stats["corrections"]
    if corrections:
        st.markdown("### Principais erros de classificação")
        import pandas as pd
        df = pd.DataFrame(corrections)
        df.columns = ["Tipo Original", "Tipo Correto", "Ocorrências"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.info(
            "💡 Com pelo menos 50 feedbacks rotulados, você pode retreinar o modelo "
            "executando `python train.py --use-feedback` na raiz do projeto."
        )


def _render_access_log(conn: sqlite3.Connection) -> None:
    import pandas as pd
    rows = conn.execute(
        "SELECT accessed_at, action, patient_hash, session_id "
        "FROM access_log ORDER BY accessed_at DESC LIMIT 200"
    ).fetchall()

    if not rows:
        st.info("Nenhum acesso registrado.")
        return

    df = pd.DataFrame([dict(r) for r in rows])
    df["accessed_at"]  = pd.to_datetime(df["accessed_at"]).dt.strftime("%d/%m/%Y %H:%M:%S")
    df["patient_hash"] = df["patient_hash"].fillna("—").apply(
        lambda v: v[:16] + "…" if len(str(v)) > 16 else v
    )
    df["session_id"] = df["session_id"].fillna("—").apply(
        lambda v: v[:12] + "…" if len(str(v)) > 12 else v
    )
    df.columns = ["Data/Hora", "Ação", "Paciente (hash)", "Sessão"]
    st.dataframe(df, use_container_width=True, hide_index=True)
