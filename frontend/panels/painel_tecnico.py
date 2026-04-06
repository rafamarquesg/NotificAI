"""
Estação de Trabalho do Técnico NUVE — redesign moderno.
"""

import hashlib
import os
import sqlite3
import uuid
from typing import Optional

import streamlit as st

from core.database import (
    get_analysis_detail, get_detections, log_access,
    priority_queue_filtered, get_patient_timeline,
)
from components.case_worklist import render_worklist
from components.text_viewer import render_text_viewer
from components.decision_panel import render_decision_panel
from components.sinan_form import render_sinan_form
from components.upload_widget import render_upload_section

_DEFAULT_HASH = os.environ.get(
    "NOTIFICAI_ADMIN_HASH",
    hashlib.sha256(b"notificai2024").hexdigest(),
)

_SEV_COLOR = {
    "CRÍTICO": "#EF4444", "ALTO": "#F97316",
    "MODERADO": "#EAB308", "BAIXO": "#3B82F6",
}
_SEV_GLOW = {
    "CRÍTICO": "rgba(239,68,68,0.25)", "ALTO": "rgba(249,115,22,0.2)",
    "MODERADO": "rgba(234,179,8,0.2)", "BAIXO": "rgba(59,130,246,0.15)",
}


def _check_pw(pw: str) -> bool:
    return hashlib.sha256(pw.encode()).hexdigest() == _DEFAULT_HASH


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def _login() -> None:
    st.markdown("""
    <div style="
        min-height:70vh; display:flex; align-items:center; justify-content:center;
    ">
        <div style="
            background:linear-gradient(145deg,#141C2E,#0F1623);
            border:1px solid rgba(255,255,255,0.07);
            border-radius:20px; padding:48px 52px;
            width:100%; max-width:420px;
            box-shadow:0 24px 64px rgba(0,0,0,0.5);
            text-align:center;
        ">
            <div style="
                width:56px;height:56px;margin:0 auto 20px;
                background:linear-gradient(135deg,#3B82F6,#1D4ED8);
                border-radius:16px;display:flex;align-items:center;
                justify-content:center;font-size:1.6rem;
                box-shadow:0 8px 24px rgba(59,130,246,0.4);
            ">🏥</div>
            <div style="color:#F1F5F9;font-size:1.4rem;font-weight:700;margin-bottom:4px;">
                NotificAI
            </div>
            <div style="color:#4B5563;font-size:0.83rem;margin-bottom:32px;">
                Estação de Trabalho · NUVE HC-FMUSP
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        with st.form("tecnico_login", clear_on_submit=False):
            pw = st.text_input("Senha de acesso", type="password",
                               placeholder="••••••••••••",
                               label_visibility="collapsed")
            ok = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if ok:
            if _check_pw(pw):
                st.session_state["tecnico_auth"] = True
                st.session_state["tecnico_session_id"] = str(uuid.uuid4())
                st.rerun()
            else:
                st.error("Senha incorreta.")


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------
def render(conn: sqlite3.Connection) -> None:
    if not st.session_state.get("tecnico_auth"):
        _login()
        return

    sid: str = st.session_state.get("tecnico_session_id", "")
    log_access(conn, "view_tecnico_panel", session_id=sid)

    _topbar(conn, sid)

    col_left, col_right = st.columns([1, 3], gap="medium")

    with col_left:
        def _sel(aid: str):
            st.session_state["tecnico_case_id"]    = aid
            st.session_state["tecnico_show_sinan"] = False
            for k in list(st.session_state):
                if k.startswith("dp_action_"):
                    del st.session_state[k]

        render_worklist(conn, on_select=_sel,
                        selected_id=st.session_state.get("tecnico_case_id"))

    with col_right:
        cid: Optional[str] = st.session_state.get("tecnico_case_id")
        if not cid:
            _empty_state()
        else:
            _case_view(conn, cid, sid)


# ---------------------------------------------------------------------------
# Topbar
# ---------------------------------------------------------------------------
def _topbar(conn: sqlite3.Connection, sid: str) -> None:
    c1, c2, c3, c4 = st.columns([3, 1.2, 0.7, 0.5], gap="small")

    c1.markdown("""
    <div style="padding-top:6px;">
        <span style="color:#F1F5F9;font-size:1rem;font-weight:600;">
            Estação de Trabalho
        </span>
        <span style="color:#374151;font-size:0.8rem;margin-left:8px;">
            Técnico NUVE
        </span>
    </div>
    """, unsafe_allow_html=True)

    with c2.expander("📂 Inserir documento"):
        render_upload_section(conn)

    if c3.button("🔄 Atualizar", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

    if c4.button("Sair", use_container_width=True):
        log_access(conn, "logout_tecnico", session_id=sid)
        for k in ["tecnico_auth", "tecnico_session_id", "tecnico_case_id"]:
            st.session_state.pop(k, None)
        st.rerun()

    st.markdown("<hr style='margin:8px 0 0;'>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Estado vazio
# ---------------------------------------------------------------------------
def _empty_state() -> None:
    st.markdown("""
    <div style="
        display:flex;flex-direction:column;align-items:center;justify-content:center;
        min-height:60vh;text-align:center;padding:40px;
    ">
        <div style="
            width:72px;height:72px;
            background:rgba(59,130,246,0.08);
            border:1px solid rgba(59,130,246,0.15);
            border-radius:20px;
            display:flex;align-items:center;justify-content:center;
            font-size:2rem;margin-bottom:20px;
        ">📋</div>
        <div style="color:#E2E8F0;font-size:1.05rem;font-weight:600;margin-bottom:8px;">
            Nenhum caso selecionado
        </div>
        <div style="color:#4B5563;font-size:0.85rem;max-width:320px;line-height:1.6;">
            Selecione um caso na fila à esquerda para iniciar a revisão.
            Casos <span style="color:#EF4444;font-weight:600;">CRÍTICOS</span>
            têm prioridade máxima.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Visualização do caso
# ---------------------------------------------------------------------------
def _case_view(conn: sqlite3.Connection, cid: str, sid: str) -> None:
    detail = get_analysis_detail(conn, cid)
    if not detail:
        st.warning("Caso não encontrado.")
        st.session_state.pop("tecnico_case_id", None)
        return

    log_access(conn, "view_case", patient_hash=detail.get("patient_hash"), session_id=sid)

    ntype    = detail.get("notification_type", "—")
    score    = detail.get("score", 0.0)
    conf     = detail.get("confidence", 0.0)
    severity = detail.get("severity_level", "—")
    fname    = detail.get("filename", "—")
    doc_type = detail.get("document_type") or "—"
    status   = detail.get("case_status", "pendente")

    col  = _SEV_COLOR.get(severity, "#6B7280")
    glow = _SEV_GLOW.get(severity, "rgba(107,114,128,0.1)")
    score_pct = min(int(score / 25 * 100), 100)

    # ── Cabeçalho do caso ─────────────────────────────────────────────
    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#141C2E,#0F1623);
        border:1px solid rgba(255,255,255,0.07);
        border-left:4px solid {col};
        border-radius:0 12px 12px 0;
        padding:16px 20px;
        margin-bottom:16px;
        box-shadow:inset 4px 0 20px {glow};
    ">
        <div style="display:flex;flex-wrap:wrap;gap:24px;align-items:center;">

            <div style="flex:1;min-width:180px;">
                <div style="color:#4B5563;font-size:0.68rem;text-transform:uppercase;
                    letter-spacing:0.07em;margin-bottom:3px;">Documento</div>
                <div style="color:#F1F5F9;font-size:0.9rem;font-weight:600;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px;">
                    {fname}
                </div>
                <div style="color:#4B5563;font-size:0.75rem;margin-top:1px;">{doc_type}</div>
            </div>

            <div>
                <div style="color:#4B5563;font-size:0.68rem;text-transform:uppercase;
                    letter-spacing:0.07em;margin-bottom:3px;">Classificação IA</div>
                <div style="color:#60A5FA;font-size:0.9rem;font-weight:600;">{ntype}</div>
                <div style="color:#4B5563;font-size:0.75rem;margin-top:1px;">
                    {conf:.0%} de confiança
                </div>
            </div>

            <div>
                <div style="color:#4B5563;font-size:0.68rem;text-transform:uppercase;
                    letter-spacing:0.07em;margin-bottom:3px;">Score / Severidade</div>
                <div style="color:{col};font-size:0.95rem;font-weight:700;
                    text-shadow:0 0 12px {col}88;">{severity}</div>
                <div style="background:rgba(255,255,255,0.07);border-radius:4px;
                    height:4px;width:80px;margin-top:5px;">
                    <div style="background:{col};width:{score_pct}%;
                        height:4px;border-radius:4px;opacity:0.9;"></div>
                </div>
                <div style="color:#4B5563;font-size:0.7rem;margin-top:2px;">{score:.1f} pts</div>
            </div>

            <div>
                <div style="color:#4B5563;font-size:0.68rem;text-transform:uppercase;
                    letter-spacing:0.07em;margin-bottom:5px;">Status</div>
                <div style="
                    display:inline-block;
                    background:rgba(255,255,255,0.06);
                    border:1px solid rgba(255,255,255,0.1);
                    border-radius:20px;padding:3px 12px;
                    color:#94A3B8;font-size:0.78rem;font-weight:500;
                ">{status.upper()}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Abas ──────────────────────────────────────────────────────────
    tab_a, tab_s, tab_h = st.tabs([
        "🔍  Análise & Decisão",
        "📋  Ficha SINAN",
        "⏱️  Histórico do Paciente",
    ])

    with tab_a:
        _tab_analysis(conn, cid, sid, detail)

    with tab_s:
        if st.session_state.get("tecnico_show_sinan") or status == "notificado":
            render_sinan_form(conn, cid, sid, show_patient=True)
        else:
            st.markdown("""
            <div style="
                background:rgba(59,130,246,0.06);
                border:1px solid rgba(59,130,246,0.15);
                border-radius:12px;padding:32px;text-align:center;margin:12px 0;
            ">
                <div style="font-size:2rem;margin-bottom:10px;">📋</div>
                <div style="color:#93C5FD;font-weight:600;margin-bottom:6px;">
                    Ficha SINAN disponível após confirmação
                </div>
                <div style="color:#4B5563;font-size:0.83rem;">
                    Confirme ou reclassifique o caso na aba <strong>Análise & Decisão</strong>.
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Abrir ficha mesmo assim", key=f"force_sinan_{cid}"):
                st.session_state["tecnico_show_sinan"] = True
                st.rerun()

    with tab_h:
        _tab_history(conn, detail, cid, sid)


# ---------------------------------------------------------------------------
# Aba Análise
# ---------------------------------------------------------------------------
def _tab_analysis(conn, cid, sid, detail):
    detections = get_detections(conn, cid)
    active  = [d for d in detections if not d.get("negated")]
    negated = [d for d in detections if d.get("negated")]

    # Mini-stats das detecções
    st.markdown(f"""
    <div style="display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;">
        <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);
            border-radius:8px;padding:8px 14px;text-align:center;">
            <div style="color:#EF4444;font-size:1.1rem;font-weight:700;">{len(active)}</div>
            <div style="color:#4B5563;font-size:0.7rem;">termos ativos</div>
        </div>
        <div style="background:rgba(107,114,128,0.08);border:1px solid rgba(107,114,128,0.15);
            border-radius:8px;padding:8px 14px;text-align:center;">
            <div style="color:#9CA3AF;font-size:1.1rem;font-weight:700;">{len(negated)}</div>
            <div style="color:#4B5563;font-size:0.7rem;">negados</div>
        </div>
        <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.15);
            border-radius:8px;padding:8px 14px;text-align:center;">
            <div style="color:#60A5FA;font-size:1.1rem;font-weight:700;">
                {len(set(d['category'] for d in active))}
            </div>
            <div style="color:#4B5563;font-size:0.7rem;">categorias</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_text_viewer(conn, cid)
    st.markdown("<hr>", unsafe_allow_html=True)

    def _next():
        cases = priority_queue_filtered(conn, limit=50, status_filter="pendente")
        others = [c for c in cases if c["analysis_id"] != cid]
        if others:
            st.session_state["tecnico_case_id"]    = others[0]["analysis_id"]
            st.session_state["tecnico_show_sinan"] = False
            for k in list(st.session_state):
                if k.startswith("dp_action_"):
                    del st.session_state[k]
            st.rerun()
        else:
            st.success("🎉 Nenhum caso pendente restante.")

    render_decision_panel(conn, cid, sid,
        on_confirmed=lambda: st.session_state.update({"tecnico_show_sinan": True}),
        on_next_case=_next,
    )


# ---------------------------------------------------------------------------
# Aba Histórico
# ---------------------------------------------------------------------------
def _tab_history(conn, detail, cid, sid):
    from components.timeline_viewer import render_patient_timeline
    ph = detail.get("patient_hash") or ""
    if not ph:
        st.info("Hash do paciente não disponível.")
        return

    log_access(conn, "view_patient_history", patient_hash=ph, session_id=sid)
    timeline = get_patient_timeline(conn, ph)
    prev = [t for t in timeline if t["analysis_id"] != cid]

    if prev:
        st.markdown(f"""
        <div style="
            background:rgba(249,115,22,0.08);
            border:1px solid rgba(249,115,22,0.25);
            border-left:4px solid #F97316;
            border-radius:0 10px 10px 0;
            padding:12px 16px;margin-bottom:14px;
        ">
            <div style="color:#FB923C;font-weight:600;font-size:0.88rem;">
                ⚠️ Reincidência detectada
            </div>
            <div style="color:#4B5563;font-size:0.82rem;margin-top:2px;">
                Este paciente possui <strong style="color:#F97316;">{len(prev)}</strong>
                ocorrência(s) anterior(es) no sistema.
            </div>
        </div>
        """, unsafe_allow_html=True)

    render_patient_timeline(conn, patient_hash=ph, session_id=sid,
        on_select_analysis=lambda aid: st.session_state.update(
            {"tecnico_case_id": aid, "tecnico_show_sinan": False}
        ),
    )
