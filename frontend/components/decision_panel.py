"""
Painel de decisão do técnico — CONFIRMAR / RECLASSIFICAR / ARQUIVAR.

Exibido imediatamente abaixo da análise da IA, sempre visível.
Registra a decisão no banco e dispara callbacks para atualizar a UI.
"""

import sqlite3
import uuid
from typing import Callable, Optional

import streamlit as st

from core.database import (
    update_case_status,
    add_feedback,
    get_analysis_detail,
    CASE_STATUSES,
)

_ALL_TYPES = [
    "Violência Física",
    "Violência Sexual",
    "Violência Psicológica/Moral",
    "Violência Autoprovocada",
    "Negligência/Abandono",
    "Trabalho Infantil",
    "Tráfico de Pessoas",
    "Outros/Não Classificado",
]

_STATUS_COLOR = {
    "pendente":   "#e74c3c",
    "em análise": "#3498db",
    "notificado": "#27ae60",
    "arquivado":  "#7f8c8d",
}


def render_decision_panel(
    conn: sqlite3.Connection,
    analysis_id: str,
    session_id: str,
    on_confirmed: Optional[Callable[[], None]] = None,
    on_next_case: Optional[Callable[[], None]] = None,
) -> None:
    """
    Renderiza o painel de decisão para um caso.

    Args:
        conn:         Conexão SQLite.
        analysis_id:  ID da análise em revisão.
        session_id:   ID da sessão autenticada (para log de auditoria).
        on_confirmed: Callback chamado após CONFIRMAR E NOTIFICAR.
        on_next_case: Callback para avançar ao próximo caso na fila.
    """
    detail = get_analysis_detail(conn, analysis_id)
    if not detail:
        return

    current_status = detail.get("case_status", "pendente")
    ai_type        = detail.get("notification_type", "—")
    confidence     = detail.get("confidence", 0.0)
    assigned_to    = detail.get("assigned_to") or ""

    # ------------------------------------------------------------------
    # Resumo da IA
    # ------------------------------------------------------------------
    color = _STATUS_COLOR.get(current_status, "#7f8c8d")

    st.markdown(
        f"""
        <div style="
            background:#1e2c3a;
            border-radius:10px;
            padding:14px 18px;
            margin-bottom:12px;
        ">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="color:#7f8c8d;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;">
                        Classificação da IA
                    </div>
                    <div style="color:#ecf0f1;font-size:1.05rem;font-weight:700;margin-top:2px;">
                        {ai_type}
                    </div>
                    <div style="color:#7f8c8d;font-size:0.82rem;margin-top:2px;">
                        Confiança: <strong style="color:#ecf0f1;">{confidence:.0%}</strong>
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="color:#7f8c8d;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;">
                        Status atual
                    </div>
                    <div style="
                        background:{color};
                        color:white;
                        padding:4px 12px;
                        border-radius:20px;
                        font-size:0.82rem;
                        font-weight:600;
                        margin-top:4px;
                        display:inline-block;
                    ">{current_status.upper()}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Já notificado — exibir apenas próximo caso
    # ------------------------------------------------------------------
    if current_status == "notificado":
        st.success("✅ Este caso já foi notificado ao SINAN.")
        if on_next_case:
            if st.button("▶ Próximo caso", key=f"dp_next_{analysis_id}", use_container_width=True):
                on_next_case()
        return

    if current_status == "arquivado":
        st.info("📁 Este caso foi arquivado.")
        col_reopen, col_next = st.columns(2)
        if col_reopen.button("↩ Reabrir", key=f"dp_reopen_{analysis_id}", use_container_width=True):
            update_case_status(conn, analysis_id, "pendente", notes="Reaberto pelo técnico")
            st.rerun()
        if on_next_case and col_next.button("▶ Próximo", key=f"dp_next_arch_{analysis_id}", use_container_width=True):
            on_next_case()
        return

    # ------------------------------------------------------------------
    # Marcar como "em análise" automaticamente ao abrir
    # ------------------------------------------------------------------
    if current_status == "pendente":
        update_case_status(conn, analysis_id, "em análise", assigned_to=assigned_to or None)

    # ------------------------------------------------------------------
    # Ações principais
    # ------------------------------------------------------------------
    st.markdown("#### Decisão do técnico")

    col_confirm, col_reclassify, col_archive = st.columns(3)

    # — CONFIRMAR E NOTIFICAR —
    with col_confirm:
        if st.button(
            "✅ Confirmar e Notificar",
            key=f"dp_confirm_{analysis_id}",
            type="primary",
            use_container_width=True,
            help="Confirma a classificação da IA e marca o caso como notificado.",
        ):
            st.session_state[f"dp_action_{analysis_id}"] = "confirm"

    # — RECLASSIFICAR —
    with col_reclassify:
        if st.button(
            "✏️ Reclassificar",
            key=f"dp_reclassify_{analysis_id}",
            use_container_width=True,
            help="Corrige o tipo de notificação identificado pela IA.",
        ):
            st.session_state[f"dp_action_{analysis_id}"] = "reclassify"

    # — ARQUIVAR —
    with col_archive:
        if st.button(
            "📁 Arquivar",
            key=f"dp_archive_{analysis_id}",
            use_container_width=True,
            help="Arquiva o caso sem notificação (não é violência ou texto insuficiente).",
        ):
            st.session_state[f"dp_action_{analysis_id}"] = "archive"

    # ------------------------------------------------------------------
    # Sub-formulários por ação
    # ------------------------------------------------------------------
    action = st.session_state.get(f"dp_action_{analysis_id}")

    if action == "confirm":
        _confirm_form(conn, analysis_id, ai_type, session_id, on_confirmed, on_next_case)

    elif action == "reclassify":
        _reclassify_form(conn, analysis_id, ai_type, session_id, on_next_case)

    elif action == "archive":
        _archive_form(conn, analysis_id, session_id, on_next_case)

    # ------------------------------------------------------------------
    # Botão "Próximo caso" sempre disponível
    # ------------------------------------------------------------------
    if on_next_case and action is None:
        st.markdown("---")
        if st.button(
            "▶ Próximo caso na fila",
            key=f"dp_next_main_{analysis_id}",
            use_container_width=True,
        ):
            on_next_case()


# ---------------------------------------------------------------------------
# Sub-formulários
# ---------------------------------------------------------------------------

def _confirm_form(
    conn, analysis_id, ai_type, session_id, on_confirmed, on_next_case
):
    st.markdown("---")
    with st.container():
        st.markdown(
            f"""
            <div style="background:#d5f5e3;border:1px solid #27ae60;border-radius:8px;padding:12px 16px;margin-bottom:10px;">
                <strong>Confirmar notificação:</strong><br/>
                Tipo: <strong>{ai_type}</strong><br/>
                <span style="font-size:0.83rem;color:#555;">
                    Após confirmar, o caso será marcado como <em>notificado</em> e
                    a ficha SINAN ficará disponível para download.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        tech_name = st.text_input(
            "Seu nome (opcional)",
            key=f"conf_tech_{analysis_id}",
            placeholder="Ex.: Ana Silva",
        )
        notes = st.text_area(
            "Observações (opcional)",
            key=f"conf_notes_{analysis_id}",
            placeholder="Notas adicionais sobre o caso…",
            height=70,
        )
        col_ok, col_cancel = st.columns(2)
        if col_ok.button(
            "✅ Confirmar", key=f"conf_ok_{analysis_id}", type="primary", use_container_width=True
        ):
            add_feedback(
                conn, analysis_id,
                original_type=ai_type,
                corrected_type=ai_type,
                correct=True,
                session_id=session_id,
            )
            update_case_status(
                conn, analysis_id, "notificado",
                assigned_to=tech_name or None,
                notes=notes or None,
            )
            st.session_state.pop(f"dp_action_{analysis_id}", None)
            st.session_state["tecnico_show_sinan"] = True
            st.success("Caso notificado. Baixe a ficha SINAN abaixo.")
            if on_confirmed:
                on_confirmed()
            st.rerun()
        if col_cancel.button("Cancelar", key=f"conf_cancel_{analysis_id}", use_container_width=True):
            st.session_state.pop(f"dp_action_{analysis_id}", None)
            st.rerun()


def _reclassify_form(conn, analysis_id, ai_type, session_id, on_next_case):
    st.markdown("---")
    with st.container():
        st.markdown("**Corrigir classificação:**")
        corrected = st.selectbox(
            "Tipo correto",
            _ALL_TYPES,
            index=_ALL_TYPES.index(ai_type) if ai_type in _ALL_TYPES else 0,
            key=f"reclassify_type_{analysis_id}",
        )
        reason = st.text_area(
            "Motivo da correção",
            key=f"reclassify_reason_{analysis_id}",
            placeholder="Descreva por que a classificação da IA está incorreta…",
            height=70,
        )
        col_ok, col_cancel = st.columns(2)
        if col_ok.button(
            "Salvar e Notificar", key=f"reclassify_ok_{analysis_id}",
            type="primary", use_container_width=True,
        ):
            add_feedback(
                conn, analysis_id,
                original_type=ai_type,
                corrected_type=corrected,
                correct=(corrected == ai_type),
                session_id=session_id,
            )
            # Atualiza tipo na análise
            conn.execute(
                "UPDATE analyses SET notification_type = ? WHERE analysis_id = ?",
                (corrected, analysis_id),
            )
            conn.commit()
            update_case_status(
                conn, analysis_id, "notificado",
                notes=f"Reclassificado de '{ai_type}' para '{corrected}'. {reason}",
            )
            st.session_state.pop(f"dp_action_{analysis_id}", None)
            st.session_state["tecnico_show_sinan"] = True
            st.success(f"Reclassificado para: {corrected}")
            st.rerun()
        if col_cancel.button("Cancelar", key=f"reclassify_cancel_{analysis_id}", use_container_width=True):
            st.session_state.pop(f"dp_action_{analysis_id}", None)
            st.rerun()


def _archive_form(conn, analysis_id, session_id, on_next_case):
    st.markdown("---")
    with st.container():
        st.markdown(
            """
            <div style="background:#fef9e7;border:1px solid #f39c12;border-radius:8px;padding:12px 16px;margin-bottom:10px;">
                <strong>Arquivar sem notificação</strong><br/>
                <span style="font-size:0.83rem;color:#555;">
                    Use quando o texto não indica violência real ou é insuficiente para notificação.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        reason_options = [
            "Texto insuficiente / legibilidade ruim",
            "Suspeita descartada pelo clínico",
            "Duplicata de notificação já realizada",
            "Termos fora de contexto de violência",
            "Outro",
        ]
        reason = st.selectbox("Motivo", reason_options, key=f"archive_reason_{analysis_id}")
        notes = st.text_area(
            "Observações adicionais",
            key=f"archive_notes_{analysis_id}",
            height=60,
        )
        add_feedback(
            conn, analysis_id,
            original_type="—",
            corrected_type="Outros/Não Classificado",
            correct=False,
            session_id=session_id,
        ) if False else None  # registra apenas ao confirmar

        col_ok, col_cancel = st.columns(2)
        if col_ok.button(
            "📁 Arquivar", key=f"archive_ok_{analysis_id}",
            use_container_width=True,
        ):
            update_case_status(
                conn, analysis_id, "arquivado",
                notes=f"{reason}. {notes}".strip(". "),
            )
            st.session_state.pop(f"dp_action_{analysis_id}", None)
            st.success("Caso arquivado.")
            if on_next_case:
                on_next_case()
            st.rerun()
        if col_cancel.button("Cancelar", key=f"archive_cancel_{analysis_id}", use_container_width=True):
            st.session_state.pop(f"dp_action_{analysis_id}", None)
            st.rerun()
