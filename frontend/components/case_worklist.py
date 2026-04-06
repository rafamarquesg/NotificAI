"""
Worklist de triagem — lista de casos pendentes com código de cor por severidade.

Exibe na coluna esquerda da Estação de Trabalho do Técnico.
Permite selecionar um caso para análise com um clique.
"""

import sqlite3
from typing import Callable, Optional

import streamlit as st

from core.database import priority_queue_filtered, count_by_status, CASE_STATUSES

# Mapeamento de severidade → cor e emoji
_SEVERITY_CONFIG = {
    "CRÍTICO":       {"color": "#e74c3c", "emoji": "🔴", "order": 0},
    "ALTO":          {"color": "#e67e22", "emoji": "🟠", "order": 1},
    "MODERADO":      {"color": "#f1c40f", "emoji": "🟡", "order": 2},
    "BAIXO":         {"color": "#3498db", "emoji": "🔵", "order": 3},
    "MÍNIMO":        {"color": "#95a5a6", "emoji": "⚪", "order": 4},
    "SEM INDICAÇÃO": {"color": "#bdc3c7", "emoji": "⚫", "order": 5},
}

_STATUS_LABEL = {
    "pendente":   "⏳ Pendente",
    "em análise": "🔍 Em análise",
    "notificado": "✅ Notificado",
    "arquivado":  "📁 Arquivado",
}


def render_worklist(
    conn: sqlite3.Connection,
    on_select: Callable[[str], None],
    selected_id: Optional[str] = None,
) -> None:
    """
    Renderiza a coluna de triagem (worklist).

    Args:
        conn:        Conexão SQLite.
        on_select:   Callback chamado com analysis_id ao clicar num caso.
        selected_id: ID do caso atualmente selecionado (destacado na lista).
    """

    # ------------------------------------------------------------------
    # Cabeçalho + contadores de status
    # ------------------------------------------------------------------
    status_counts = {r["case_status"]: r["total"] for r in count_by_status(conn)}
    pending  = status_counts.get("pendente",   0)
    analise  = status_counts.get("em análise", 0)
    notif    = status_counts.get("notificado", 0)

    st.markdown(
        f"""
        <div style="
            background: #1e2c3a;
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 10px;
        ">
            <div style="color:#ecf0f1;font-size:1rem;font-weight:600;margin-bottom:6px;">
                📋 Fila de Trabalho
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
                <span style="background:#e74c3c;color:white;padding:2px 8px;border-radius:12px;font-size:0.78rem;">
                    ⏳ {pending} pendentes
                </span>
                <span style="background:#3498db;color:white;padding:2px 8px;border-radius:12px;font-size:0.78rem;">
                    🔍 {analise} em análise
                </span>
                <span style="background:#27ae60;color:white;padding:2px 8px;border-radius:12px;font-size:0.78rem;">
                    ✅ {notif} notificados
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Filtros rápidos
    # ------------------------------------------------------------------
    with st.expander("🔎 Filtros", expanded=False):
        col_s, col_t = st.columns(2)
        status_filter = col_s.selectbox(
            "Status",
            ["pendente", "em análise", "notificado", "arquivado", "(todos)"],
            index=0,
            key="wl_status",
            label_visibility="collapsed",
        )
        severity_filter = col_t.selectbox(
            "Severidade",
            ["(todas)", "CRÍTICO", "ALTO", "MODERADO", "BAIXO"],
            key="wl_severity",
            label_visibility="collapsed",
        )
        limit = st.slider("Máx. casos", 10, 100, 30, step=10, key="wl_limit")

    sf = None if status_filter == "(todos)" else status_filter
    sv = None if severity_filter == "(todas)" else severity_filter

    # ------------------------------------------------------------------
    # Lista de casos
    # ------------------------------------------------------------------
    cases = priority_queue_filtered(conn, limit=limit, status_filter=sf, severity_filter=sv)

    if not cases:
        st.info("Nenhum caso encontrado com os filtros aplicados.")
        return

    st.markdown(
        f"<div style='color:#7f8c8d;font-size:0.8rem;margin-bottom:6px;'>"
        f"{len(cases)} caso(s) encontrado(s)</div>",
        unsafe_allow_html=True,
    )

    for case in cases:
        _render_case_card(case, on_select, selected_id)


def _render_case_card(
    case: dict,
    on_select: Callable[[str], None],
    selected_id: Optional[str],
) -> None:
    """Renderiza o card de um caso na worklist."""
    aid        = case["analysis_id"]
    severity   = case.get("severity_level", "SEM INDICAÇÃO")
    ntype      = case.get("notification_type", "—")
    score      = case.get("score", 0.0)
    confidence = case.get("confidence", 0.0)
    filename   = case.get("filename", "—")
    doc_date   = case.get("document_date") or "—"
    case_status = case.get("case_status", "pendente")

    cfg   = _SEVERITY_CONFIG.get(severity, _SEVERITY_CONFIG["SEM INDICAÇÃO"])
    color = cfg["color"]
    emoji = cfg["emoji"]

    is_selected = (aid == selected_id)
    bg_color = "#1a3a4a" if is_selected else "#1e2c3a"
    border   = f"2px solid {color}" if is_selected else f"2px solid {color}44"

    # Truncar nome do arquivo
    fname_display = filename if len(filename) <= 30 else filename[:27] + "…"
    # Truncar tipo
    ntype_short = ntype.replace("Violência ", "V. ").replace("/Moral", "").replace("/Abandono", "")

    # Score bar (0–30 max para visualização)
    score_pct = min(int(score / 30 * 100), 100)
    bar_color = color

    card_html = f"""
    <div style="
        background:{bg_color};
        border:{border};
        border-radius:8px;
        padding:9px 11px;
        margin-bottom:6px;
        cursor:pointer;
    ">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="color:{color};font-weight:700;font-size:0.85rem;">
                {emoji} {severity}
            </span>
            <span style="color:#7f8c8d;font-size:0.72rem;">{_STATUS_LABEL.get(case_status, case_status)}</span>
        </div>
        <div style="color:#ecf0f1;font-size:0.82rem;margin:3px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
            {fname_display}
        </div>
        <div style="color:#bdc3c7;font-size:0.78rem;">{ntype_short} · {confidence:.0%}</div>
        <div style="background:#2c3e50;border-radius:4px;height:4px;margin-top:5px;">
            <div style="background:{bar_color};width:{score_pct}%;height:4px;border-radius:4px;"></div>
        </div>
        <div style="color:#7f8c8d;font-size:0.7rem;margin-top:2px;">
            Score {score:.1f} · {doc_date}
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    btn_label = "▶ Aberto" if is_selected else "Abrir"
    btn_type  = "primary" if is_selected else "secondary"
    if st.button(btn_label, key=f"wl_btn_{aid}", type=btn_type, use_container_width=True):
        on_select(aid)
