"""
Estação de Trabalho do Técnico NUVE — tela principal de revisão de casos.

Design de tela única (sem troca de abas para o fluxo principal):
  - Coluna esquerda  : Worklist de triagem com código de cor por severidade
  - Coluna direita   : Caso selecionado — análise da IA + decisão + ficha SINAN

Fluxo do técnico:
  1. Abre o NotificAI → vê fila priorizada por score
  2. Clica em um caso → vê texto com termos destacados + análise da IA
  3. Decide: CONFIRMAR / RECLASSIFICAR / ARQUIVAR
  4. Após confirmar → baixa ficha SINAN pré-preenchida
  5. Clica "Próximo caso" → retorna automaticamente para o próximo pendente
"""

import hashlib
import os
import sqlite3
import uuid
from typing import Optional

import streamlit as st

from core.database import (
    get_analysis_detail,
    get_detections,
    log_access,
    priority_queue_filtered,
)
from components.case_worklist import render_worklist
from components.text_viewer import render_text_viewer
from components.decision_panel import render_decision_panel
from components.sinan_form import render_sinan_form
from components.upload_widget import render_upload_section

# ---------------------------------------------------------------------------
# Autenticação (reutiliza a mesma senha do Painel Seguro)
# ---------------------------------------------------------------------------

_DEFAULT_PASSWORD_HASH = os.environ.get(
    "NOTIFICAI_ADMIN_HASH",
    hashlib.sha256(b"notificai2024").hexdigest(),
)


def _check_password(password: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == _DEFAULT_PASSWORD_HASH


def _login_form() -> None:
    st.markdown(
        """
        <div style="
            max-width:420px;
            margin:60px auto 0;
            background:#1e2c3a;
            border-radius:12px;
            padding:32px 36px;
            text-align:center;
        ">
            <div style="font-size:2.5rem;">🏥</div>
            <h2 style="color:#ecf0f1;margin:8px 0 4px;">NotificAI</h2>
            <p style="color:#7f8c8d;font-size:0.9rem;">
                Estação de Trabalho NUVE — Acesso Restrito
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown("")
        with st.form("tecnico_login"):
            password  = st.text_input("Senha", type="password", placeholder="Senha de acesso")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if submitted:
            if _check_password(password):
                st.session_state["tecnico_auth"]       = True
                st.session_state["tecnico_session_id"] = str(uuid.uuid4())
                st.rerun()
            else:
                st.error("Senha incorreta.")


# ---------------------------------------------------------------------------
# Painel principal
# ---------------------------------------------------------------------------

def render(conn: sqlite3.Connection) -> None:
    if not st.session_state.get("tecnico_auth"):
        _login_form()
        return

    session_id: str = st.session_state.get("tecnico_session_id", "")
    log_access(conn, "view_tecnico_panel", session_id=session_id)

    # ------------------------------------------------------------------
    # Barra superior
    # ------------------------------------------------------------------
    _render_topbar(conn, session_id)
    st.markdown(
        "<hr style='margin:0 0 12px;border-color:#2c3e50;'>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Layout principal: fila (25%) | caso (75%)
    # ------------------------------------------------------------------
    col_list, col_case = st.columns([1, 3], gap="medium")

    # ------ Coluna esquerda: worklist ------
    with col_list:
        def _select(aid: str) -> None:
            st.session_state["tecnico_case_id"]   = aid
            st.session_state["tecnico_show_sinan"] = False
            st.session_state.pop("tecnico_sinan_clicked", None)
            # Limpa ações do painel de decisão anterior
            for k in list(st.session_state.keys()):
                if k.startswith("dp_action_"):
                    del st.session_state[k]

        render_worklist(
            conn,
            on_select=_select,
            selected_id=st.session_state.get("tecnico_case_id"),
        )

    # ------ Coluna direita: caso selecionado ------
    with col_case:
        case_id: Optional[str] = st.session_state.get("tecnico_case_id")

        if not case_id:
            _render_empty_state()
        else:
            _render_case(conn, case_id, session_id)


# ---------------------------------------------------------------------------
# Barra superior
# ---------------------------------------------------------------------------

def _render_topbar(conn: sqlite3.Connection, session_id: str) -> None:
    col_logo, col_title, col_upload, col_refresh, col_logout = st.columns(
        [0.3, 2, 1.5, 0.6, 0.5], gap="small"
    )

    col_logo.markdown(
        "<div style='font-size:1.8rem;line-height:1;padding-top:6px;'>🏥</div>",
        unsafe_allow_html=True,
    )
    col_title.markdown(
        "<div style='color:#ecf0f1;font-size:1.1rem;font-weight:700;padding-top:8px;'>"
        "Estação de Trabalho — Técnico NUVE</div>",
        unsafe_allow_html=True,
    )

    with col_upload.expander("📂 Inserir documento"):
        render_upload_section(conn)

    if col_refresh.button("🔄 Atualizar", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

    if col_logout.button("Sair", use_container_width=True):
        log_access(conn, "logout_tecnico", session_id=session_id)
        st.session_state["tecnico_auth"]       = False
        st.session_state["tecnico_session_id"] = None
        st.session_state.pop("tecnico_case_id", None)
        st.rerun()


# ---------------------------------------------------------------------------
# Estado vazio
# ---------------------------------------------------------------------------

def _render_empty_state() -> None:
    st.markdown(
        """
        <div style="
            text-align:center;
            padding:80px 20px;
            color:#7f8c8d;
        ">
            <div style="font-size:4rem;">📋</div>
            <h3 style="color:#bdc3c7;">Nenhum caso selecionado</h3>
            <p>Selecione um caso na fila à esquerda para iniciar a revisão.</p>
            <p style="font-size:0.85rem;">
                Casos vermelhos são <strong style="color:#e74c3c;">CRÍTICOS</strong> e
                devem ser revisados primeiro.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Visualização do caso selecionado
# ---------------------------------------------------------------------------

def _render_case(conn: sqlite3.Connection, case_id: str, session_id: str) -> None:
    detail = get_analysis_detail(conn, case_id)
    if not detail:
        st.warning("Caso não encontrado. Pode ter sido removido.")
        st.session_state.pop("tecnico_case_id", None)
        return

    log_access(conn, "view_case", patient_hash=detail.get("patient_hash"), session_id=session_id)

    # ------------------------------------------------------------------
    # Cabeçalho do caso
    # ------------------------------------------------------------------
    ntype      = detail.get("notification_type", "—")
    score      = detail.get("score", 0.0)
    confidence = detail.get("confidence", 0.0)
    severity   = detail.get("severity_level", "—")
    filename   = detail.get("filename", "—")
    doc_type   = detail.get("document_type") or "—"
    case_status = detail.get("case_status", "pendente")

    _SEV_COLOR = {
        "CRÍTICO": "#e74c3c", "ALTO": "#e67e22",
        "MODERADO": "#f1c40f", "BAIXO": "#3498db",
    }
    sev_color = _SEV_COLOR.get(severity, "#7f8c8d")

    st.markdown(
        f"""
        <div style="
            background:#1e2c3a;
            border-left:5px solid {sev_color};
            border-radius:0 8px 8px 0;
            padding:12px 16px;
            margin-bottom:12px;
            display:flex;
            flex-wrap:wrap;
            gap:16px;
            align-items:center;
        ">
            <div>
                <div style="color:#7f8c8d;font-size:0.72rem;text-transform:uppercase;">Documento</div>
                <div style="color:#ecf0f1;font-size:0.9rem;font-weight:600;max-width:260px;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{filename}</div>
                <div style="color:#7f8c8d;font-size:0.78rem;">{doc_type}</div>
            </div>
            <div>
                <div style="color:#7f8c8d;font-size:0.72rem;text-transform:uppercase;">Classificação IA</div>
                <div style="color:#ecf0f1;font-size:0.9rem;font-weight:600;">{ntype}</div>
                <div style="color:#7f8c8d;font-size:0.78rem;">confiança {confidence:.0%}</div>
            </div>
            <div>
                <div style="color:#7f8c8d;font-size:0.72rem;text-transform:uppercase;">Score / Severidade</div>
                <div style="color:{sev_color};font-size:0.95rem;font-weight:700;">{severity}</div>
                <div style="color:#7f8c8d;font-size:0.78rem;">{score:.1f} pts</div>
            </div>
            <div>
                <div style="color:#7f8c8d;font-size:0.72rem;text-transform:uppercase;">Status</div>
                <div style="color:#ecf0f1;font-size:0.85rem;">{case_status.upper()}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Abas internas (sem abandonar o caso)
    # ------------------------------------------------------------------
    tab_analysis, tab_sinan, tab_history = st.tabs([
        "🔍 Análise & Decisão",
        "📋 Ficha SINAN",
        "⏱️ Histórico do Paciente",
    ])

    with tab_analysis:
        _render_analysis_tab(conn, case_id, session_id, detail)

    with tab_sinan:
        show_sinan = (
            st.session_state.get("tecnico_show_sinan")
            or case_status == "notificado"
        )
        if show_sinan:
            render_sinan_form(conn, case_id, session_id, show_patient=True)
        else:
            st.info(
                "A ficha SINAN ficará disponível após **Confirmar e Notificar** "
                "na aba **Análise & Decisão**."
            )
            if st.button("Abrir ficha mesmo assim", key=f"force_sinan_{case_id}"):
                st.session_state["tecnico_show_sinan"] = True
                st.rerun()

    with tab_history:
        _render_history_tab(conn, detail, case_id, session_id)


def _render_analysis_tab(conn, case_id, session_id, detail):
    """Aba principal: texto com destaques + decisão."""
    detections = get_detections(conn, case_id)

    # Score bar visual
    score = detail.get("score", 0.0)
    score_pct = min(int(score / 30 * 100), 100)
    sev_color = {
        "CRÍTICO": "#e74c3c", "ALTO": "#e67e22",
        "MODERADO": "#f1c40f", "BAIXO": "#3498db",
    }.get(detail.get("severity_level", ""), "#7f8c8d")

    st.markdown(
        f"""
        <div style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                <span style="color:#7f8c8d;font-size:0.78rem;">Score de risco</span>
                <span style="color:{sev_color};font-size:0.78rem;font-weight:600;">
                    {score:.1f} / 30+
                </span>
            </div>
            <div style="background:#2c3e50;border-radius:6px;height:8px;">
                <div style="background:{sev_color};width:{score_pct}%;height:8px;
                    border-radius:6px;transition:width 0.3s;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Detecções em destaque
    st.markdown(f"**{len(detections)} termo(s) detectado(s)** · "
                f"{sum(1 for d in detections if not d.get('negated'))} ativos · "
                f"{sum(1 for d in detections if d.get('negated'))} negados")

    render_text_viewer(conn, case_id)

    st.markdown("---")

    # Painel de decisão
    def _next_case():
        cases = priority_queue_filtered(conn, limit=50, status_filter="pendente")
        # Encontrar o próximo na lista (excluindo o atual)
        others = [c for c in cases if c["analysis_id"] != case_id]
        if others:
            st.session_state["tecnico_case_id"]    = others[0]["analysis_id"]
            st.session_state["tecnico_show_sinan"] = False
            for k in list(st.session_state.keys()):
                if k.startswith("dp_action_"):
                    del st.session_state[k]
            st.rerun()
        else:
            st.success("🎉 Nenhum caso pendente na fila. Bom trabalho!")

    render_decision_panel(
        conn,
        analysis_id=case_id,
        session_id=session_id,
        on_confirmed=lambda: st.session_state.update({"tecnico_show_sinan": True}),
        on_next_case=_next_case,
    )


def _render_history_tab(conn, detail, case_id, session_id):
    """Aba de histórico do paciente (reincidência)."""
    from components.timeline_viewer import render_patient_timeline

    patient_hash = detail.get("patient_hash") or ""
    if not patient_hash:
        st.info("Hash do paciente não disponível.")
        return

    log_access(conn, "view_patient_history", patient_hash=patient_hash, session_id=session_id)

    # Verificar reincidência
    from core.database import get_patient_timeline
    timeline = get_patient_timeline(conn, patient_hash)
    prev = [t for t in timeline if t["analysis_id"] != case_id]

    if len(prev) > 0:
        st.warning(
            f"⚠️ **Reincidência detectada**: este paciente possui "
            f"**{len(prev)} ocorrência(s) anterior(es)** no sistema."
        )

    render_patient_timeline(
        conn,
        patient_hash=patient_hash,
        session_id=session_id,
        on_select_analysis=lambda aid: st.session_state.update(
            {"tecnico_case_id": aid, "tecnico_show_sinan": False}
        ),
    )
