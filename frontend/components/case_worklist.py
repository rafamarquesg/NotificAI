"""
Worklist de triagem — lista de casos com design moderno.
"""

import sqlite3
from typing import Callable, Optional

import streamlit as st

from core.database import priority_queue_filtered, count_by_status

_SEV = {
    "CRÍTICO":       {"color": "#EF4444", "glow": "rgba(239,68,68,0.2)",   "dot": "#EF4444", "order": 0},
    "ALTO":          {"color": "#F97316", "glow": "rgba(249,115,22,0.2)",  "dot": "#F97316", "order": 1},
    "MODERADO":      {"color": "#EAB308", "glow": "rgba(234,179,8,0.2)",   "dot": "#EAB308", "order": 2},
    "BAIXO":         {"color": "#3B82F6", "glow": "rgba(59,130,246,0.15)", "dot": "#3B82F6", "order": 3},
    "MÍNIMO":        {"color": "#6B7280", "glow": "rgba(107,114,128,0.1)", "dot": "#6B7280", "order": 4},
    "SEM INDICAÇÃO": {"color": "#374151", "glow": "rgba(55,65,81,0.1)",    "dot": "#374151", "order": 5},
}

_STATUS_PILL = {
    "pendente":   ("⏳", "#F59E0B", "rgba(245,158,11,0.12)"),
    "em análise": ("🔍", "#3B82F6", "rgba(59,130,246,0.12)"),
    "notificado": ("✅", "#10B981", "rgba(16,185,129,0.12)"),
    "arquivado":  ("📁", "#6B7280", "rgba(107,114,128,0.1)"),
}

_TYPE_SHORT = {
    "Violência Física":            "Física",
    "Violência Sexual":            "Sexual",
    "Violência Psicológica/Moral": "Psicológica",
    "Violência Autoprovocada":     "Autoprovocada",
    "Negligência/Abandono":        "Negligência",
    "Trabalho Infantil":           "Trab. Infantil",
    "Tráfico de Pessoas":          "Tráfico",
    "Outros/Não Classificado":     "Outros",
}


def render_worklist(
    conn: sqlite3.Connection,
    on_select: Callable[[str], None],
    selected_id: Optional[str] = None,
) -> None:
    status_counts = {r["case_status"]: r["total"] for r in count_by_status(conn)}
    pending  = status_counts.get("pendente",   0)
    analise  = status_counts.get("em análise", 0)
    notif    = status_counts.get("notificado", 0)

    # ── Cabeçalho da fila ─────────────────────────────────────────────
    st.markdown(f"""
    <div style="margin-bottom:14px;">
        <div style="color:#94A3B8;font-size:0.7rem;text-transform:uppercase;
            letter-spacing:0.08em;margin-bottom:8px;">Fila de Triagem</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <div style="background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.25);
                border-radius:20px;padding:3px 10px;font-size:0.72rem;color:#F59E0B;font-weight:600;">
                {pending} pendentes
            </div>
            <div style="background:rgba(59,130,246,0.12);border:1px solid rgba(59,130,246,0.25);
                border-radius:20px;padding:3px 10px;font-size:0.72rem;color:#60A5FA;font-weight:600;">
                {analise} em análise
            </div>
            <div style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.25);
                border-radius:20px;padding:3px 10px;font-size:0.72rem;color:#34D399;font-weight:600;">
                {notif} notificados
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Filtros ────────────────────────────────────────────────────────
    with st.expander("⚙️ Filtros", expanded=False):
        status_filter = st.selectbox(
            "Status", ["pendente","em análise","notificado","arquivado","(todos)"],
            key="wl_status", label_visibility="collapsed",
        )
        severity_filter = st.selectbox(
            "Severidade", ["(todas)","CRÍTICO","ALTO","MODERADO","BAIXO"],
            key="wl_severity", label_visibility="collapsed",
        )
        limit = st.slider("Máx.", 10, 100, 30, step=10, key="wl_limit")

    sf = None if status_filter == "(todos)" else status_filter
    sv = None if severity_filter == "(todas)" else severity_filter
    cases = priority_queue_filtered(conn, limit=limit, status_filter=sf, severity_filter=sv)

    if not cases:
        st.markdown("""
        <div style="text-align:center;padding:40px 10px;color:#374151;">
            <div style="font-size:2rem;margin-bottom:8px;">📭</div>
            <div style="font-size:0.83rem;">Nenhum caso encontrado</div>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown(
        f"<div style='color:#374151;font-size:0.72rem;margin-bottom:8px;'>"
        f"{len(cases)} caso(s)</div>",
        unsafe_allow_html=True,
    )

    for case in cases:
        _card(case, on_select, selected_id)


def _card(case: dict, on_select: Callable, selected_id: Optional[str]) -> None:
    aid      = case["analysis_id"]
    severity = case.get("severity_level", "SEM INDICAÇÃO")
    ntype    = _TYPE_SHORT.get(case.get("notification_type",""), "—")
    score    = case.get("score", 0.0)
    conf     = case.get("confidence", 0.0)
    fname    = case.get("filename", "—")
    doc_date = (case.get("document_date") or "")[:10]
    status   = case.get("case_status", "pendente")

    cfg  = _SEV.get(severity, _SEV["SEM INDICAÇÃO"])
    s_emoji, s_color, s_bg = _STATUS_PILL.get(status, ("•", "#6B7280", "rgba(107,114,128,0.1)"))
    is_sel = (aid == selected_id)

    fname_short = fname if len(fname) <= 26 else fname[:23] + "…"
    score_pct   = min(int(score / 25 * 100), 100)

    bg      = "rgba(59,130,246,0.08)" if is_sel else "rgba(255,255,255,0.025)"
    border  = f"1px solid {cfg['color']}55" if is_sel else f"1px solid {cfg['color']}22"
    shadow  = f"0 0 0 1px {cfg['color']}44, 0 4px 16px {cfg['glow']}" if is_sel else "none"

    st.markdown(f"""
    <div style="
        background:{bg};
        border:{border};
        border-left:3px solid {cfg['color']};
        border-radius:10px;
        padding:11px 13px;
        margin-bottom:6px;
        box-shadow:{shadow};
        transition:all 0.15s;
    ">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px;">
            <div style="display:flex;align-items:center;gap:6px;">
                <span style="
                    width:8px;height:8px;border-radius:50%;
                    background:{cfg['color']};
                    box-shadow:0 0 6px {cfg['color']};
                    flex-shrink:0;display:inline-block;
                "></span>
                <span style="color:#94A3B8;font-size:0.72rem;font-weight:600;
                    text-transform:uppercase;letter-spacing:0.04em;">{severity}</span>
            </div>
            <span style="
                background:{s_bg};color:{s_color};
                border-radius:20px;padding:2px 7px;
                font-size:0.68rem;font-weight:500;
            ">{s_emoji} {status}</span>
        </div>

        <div style="color:#E2E8F0;font-size:0.82rem;font-weight:500;
            margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
            {fname_short}
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:7px;">
            <span style="color:#60A5FA;font-size:0.75rem;">{ntype}</span>
            <span style="color:#4B5563;font-size:0.72rem;">{conf:.0%} conf.</span>
        </div>

        <div style="background:rgba(255,255,255,0.06);border-radius:4px;height:3px;margin-bottom:5px;">
            <div style="background:{cfg['color']};width:{score_pct}%;
                height:3px;border-radius:4px;opacity:0.8;"></div>
        </div>

        <div style="display:flex;justify-content:space-between;">
            <span style="color:#374151;font-size:0.7rem;">score {score:.1f}</span>
            <span style="color:#374151;font-size:0.7rem;">{doc_date}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    label = "▶ Aberto" if is_sel else "Abrir caso"
    ktype = "primary" if is_sel else "secondary"
    if st.button(label, key=f"wl_{aid}", type=ktype, use_container_width=True):
        on_select(aid)
