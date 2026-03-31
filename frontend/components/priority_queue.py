"""
Componente de fila de prioridade — tabela interativa de casos por score.

Exibe os casos mais críticos em ordem decrescente de score.
Suporta filtros por status, tipo e severidade.
Cada linha permite atualizar o workflow do caso diretamente.
"""

import sqlite3
import streamlit as st
import pandas as pd
from typing import Callable, List, Optional

from core.database import (
    priority_queue_filtered,
    update_case_status,
    count_by_status,
    CASE_STATUSES,
)


# ---------------------------------------------------------------------------
# Badges visuais
# ---------------------------------------------------------------------------

_SEV_ICON = {
    "CRÍTICO":       "🔴",
    "ALTO":          "🟠",
    "MODERADO":      "🟡",
    "BAIXO":         "🟢",
    "MÍNIMO":        "🟢",
    "SEM INDICAÇÃO": "⚪",
}

_STATUS_COLOR = {
    "pendente":    "#e74c3c",
    "em análise":  "#e67e22",
    "notificado":  "#27ae60",
    "arquivado":   "#95a5a6",
}


def _status_badge(status: str) -> str:
    color = _STATUS_COLOR.get(status, "#bdc3c7")
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:4px;font-size:0.78em;font-weight:bold">{status.upper()}</span>'
    )


# ---------------------------------------------------------------------------
# Barra de progresso do workflow
# ---------------------------------------------------------------------------

def _render_workflow_summary(conn: sqlite3.Connection) -> None:
    """Exibe contagem por status de caso como métricas horizontais."""
    rows = count_by_status(conn)
    counts = {r["case_status"]: r["total"] for r in rows}

    cols = st.columns(len(CASE_STATUSES))
    for col, status in zip(cols, CASE_STATUSES):
        color = _STATUS_COLOR.get(status, "#bdc3c7")
        col.markdown(
            f'<div style="text-align:center;padding:8px;border-radius:6px;'
            f'border:2px solid {color}">'
            f'<div style="font-size:1.5rem;font-weight:bold;color:{color}">'
            f'{counts.get(status, 0)}</div>'
            f'<div style="font-size:0.8rem;color:{color}">{status.upper()}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Componente principal
# ---------------------------------------------------------------------------

def render_priority_queue(
    conn: sqlite3.Connection,
    limit: int = 50,
    on_select: Optional[Callable[[str], None]] = None,
    show_patient_hash: bool = False,
    show_workflow_controls: bool = False,
) -> None:
    """
    Renderiza a tabela de prioridade com filtros e controles de workflow.

    Args:
        conn:                   Conexão SQLite.
        limit:                  Número máximo de casos exibidos.
        on_select:              Callback chamado com analysis_id ao clicar em "Ver".
        show_patient_hash:      Se True exibe coluna patient_hash (Painel Seguro).
        show_workflow_controls: Se True exibe controles de atualização de status.
    """
    # --- Resumo de workflow ---
    if show_workflow_controls:
        _render_workflow_summary(conn)
        st.markdown("")

    # --- Filtros ---
    with st.expander("Filtros", expanded=False):
        fc1, fc2, fc3 = st.columns(3)
        status_filter = fc1.selectbox(
            "Status", ["(todos)"] + CASE_STATUSES, key="pq_status"
        )
        type_filter = fc2.selectbox(
            "Tipo de notificação",
            ["(todos)", "Violência Física", "Violência Sexual",
             "Violência Psicológica/Moral", "Violência Autoprovocada",
             "Negligência/Abandono", "Trabalho Infantil",
             "Tráfico de Pessoas", "Outros/Não Classificado"],
            key="pq_type",
        )
        sev_filter = fc3.selectbox(
            "Severidade",
            ["(todos)", "CRÍTICO", "ALTO", "MODERADO", "BAIXO", "MÍNIMO", "SEM INDICAÇÃO"],
            key="pq_sev",
        )

    status_filter = None if status_filter == "(todos)" else status_filter
    type_filter   = None if type_filter   == "(todos)" else type_filter
    sev_filter    = None if sev_filter    == "(todos)" else sev_filter

    rows = priority_queue_filtered(
        conn,
        limit=limit,
        status_filter=status_filter,
        type_filter=type_filter,
        severity_filter=sev_filter,
    )

    if not rows:
        st.info("Nenhum caso encontrado com os filtros selecionados.")
        return

    st.markdown(f"**{len(rows)} caso(s)**")
    st.markdown("---")

    for row in rows:
        sev_icon = _SEV_ICON.get(row["severity_level"], "")

        # Linha compacta com colunas
        n_cols = 5 + (1 if show_patient_hash else 0) + (1 if on_select else 0) + (1 if show_workflow_controls else 0)
        widths  = [1, 1, 2, 2, 1]
        if show_patient_hash:
            widths.insert(3, 1)
        if show_workflow_controls:
            widths.append(2)
        if on_select:
            widths.append(1)

        cols = st.columns(widths)
        idx = 0

        cols[idx].markdown(f"{sev_icon} **{row['severity_level']}**"); idx += 1
        cols[idx].markdown(f"`{row['score']:.1f}`"); idx += 1
        cols[idx].markdown(row["notification_type"]); idx += 1
        if show_patient_hash:
            ph = str(row.get("patient_hash") or "")
            cols[idx].markdown(f"`{ph[:12]}…`" if ph else "—"); idx += 1
        cols[idx].markdown(f"📄 {row['filename']}"); idx += 1
        cols[idx].markdown(
            _status_badge(row["case_status"]), unsafe_allow_html=True
        ); idx += 1

        # Controles de workflow inline
        if show_workflow_controls:
            new_status = cols[idx].selectbox(
                "",
                CASE_STATUSES,
                index=CASE_STATUSES.index(row["case_status"])
                      if row["case_status"] in CASE_STATUSES else 0,
                key=f"ws_{row['analysis_id']}",
                label_visibility="collapsed",
            )
            if new_status != row["case_status"]:
                update_case_status(conn, row["analysis_id"], new_status)
                st.rerun()
            idx += 1

        if on_select:
            if cols[idx].button("Ver", key=f"pq_{row['analysis_id']}"):
                on_select(row["analysis_id"])

        st.markdown("---")
