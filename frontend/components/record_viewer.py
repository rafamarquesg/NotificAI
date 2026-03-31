"""
Card expandível de detalhe de análise (registro completo).

Mostra:
  - Metadados do documento (arquivo, data, páginas, tipo, qualidade)
  - Resultado da análise (tipo, severidade, score, confiança)
  - Gráfico de score por página (se houver análises por página)
  - Tabela de termos detectados
  - (Painel Seguro) Dados do paciente identificado
"""

import sqlite3
import streamlit as st
from typing import Optional

from core.database import (
    get_analysis_detail,
    get_detections,
    get_page_analyses,
    get_patient,
    log_access,
)
from components.charts import scatter_page_scores


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------

_SEVERITY_COLOR = {
    "CRÍTICO":       "#c0392b",
    "ALTO":          "#e74c3c",
    "MODERADO":      "#e67e22",
    "BAIXO":         "#f1c40f",
    "MÍNIMO":        "#2ecc71",
    "SEM INDICAÇÃO": "#95a5a6",
}

def _severity_badge(level: str) -> str:
    color = _SEVERITY_COLOR.get(level, "#bdc3c7")
    return (
        f'<span style="background:{color};color:white;padding:2px 10px;'
        f'border-radius:4px;font-size:0.85em;font-weight:bold">{level}</span>'
    )


# ---------------------------------------------------------------------------
# Componente principal
# ---------------------------------------------------------------------------

def render_record_viewer(
    conn: sqlite3.Connection,
    analysis_id: str,
    show_patient: bool = False,
    session_id: Optional[str] = None,
) -> None:
    """
    Renderiza o card de detalhe de uma análise.

    Args:
        conn:        Conexão SQLite.
        analysis_id: ID da análise a exibir.
        show_patient: Se True (Painel Seguro) exibe dados do paciente.
        session_id:  ID de sessão para log de acesso.
    """
    detail = get_analysis_detail(conn, analysis_id)
    if not detail:
        st.error("Análise não encontrada.")
        return

    st.markdown("### 📄 Detalhe do Registro")

    # --- Metadados do documento ---
    with st.expander("Metadados do Documento", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Arquivo",      detail.get("filename", "—"))
        c2.metric("Páginas",      detail.get("page_count", "—"))
        c3.metric("Tipo",         detail.get("document_type", "—"))

        c4, c5, c6 = st.columns(3)
        c4.metric("Data doc.",    detail.get("document_date") or "—")
        c5.metric("Extração",     detail.get("extraction_method", "—"))
        c6.metric("Qualidade",    detail.get("quality_level", "—"))

    # --- Resultado da análise ---
    with st.expander("Resultado da Análise", expanded=True):
        st.markdown(
            f"**Tipo de Notificação:** {detail['notification_type']}  \n"
            f"**Severidade:** {_severity_badge(detail['severity_level'])}  \n"
            f"**Score:** {detail['score']:.2f}  \n"
            f"**Confiança:** {detail['confidence']:.0%}  \n"
            f"**Modo:** {detail.get('mode', '—')}  \n"
            f"**Analisado em:** {detail['analyzed_at']}",
            unsafe_allow_html=True,
        )

    # --- Score por página ---
    page_rows = get_page_analyses(conn, detail["doc_id"])
    if page_rows:
        with st.expander("Score por Página"):
            fig = scatter_page_scores(page_rows, filename=detail.get("filename", ""))
            st.plotly_chart(fig, use_container_width=True)

    # --- Termos detectados ---
    detections = get_detections(conn, analysis_id)
    if detections:
        with st.expander(f"Termos Detectados ({len(detections)})"):
            for det in detections:
                negated = det.get("negated", 0)
                icon    = "~~" if negated else ""
                weight  = det.get("weight", 0.0)
                badge_color = "#e74c3c" if weight >= 2.5 else "#e67e22" if weight >= 1.5 else "#95a5a6"
                term_html = (
                    f'<span style="background:{badge_color};color:white;padding:1px 7px;'
                    f'border-radius:3px;font-size:0.8em">{icon}{det["term"]}{icon}</span>'
                )
                st.markdown(
                    f'{term_html} &nbsp; `{det["category"]}` &nbsp; peso: **{weight:.2f}** '
                    f'{"_(negado)_" if negated else ""}',
                    unsafe_allow_html=True,
                )
                if det.get("sentence"):
                    st.caption(f'"{det["sentence"]}"')
                st.markdown("---")
    else:
        st.info("Nenhum termo detectado para esta análise.")

    # --- Dados do paciente (Painel Seguro) ---
    if show_patient:
        patient_hash = detail.get("patient_hash")
        if patient_hash:
            log_access(conn, "view_patient", patient_hash=patient_hash, session_id=session_id)
            patient = get_patient(conn, patient_hash)
            if patient:
                with st.expander("Dados do Paciente (confidencial)", expanded=False):
                    st.warning("**Informação sensível** — acesso registrado no log de auditoria.")
                    p1, p2 = st.columns(2)
                    p1.markdown(f"**Nome:** {patient.get('nome_paciente') or '—'}")
                    p1.markdown(f"**RGHC:** {patient.get('rghc') or '—'}")
                    p2.markdown(f"**CPF:** {patient.get('cpf') or '—'}")
                    p2.markdown(f"**Nasc.:** {patient.get('data_nascimento') or '—'}")
                    st.caption(f"Hash: `{patient_hash}`")
            else:
                st.info("Dados do paciente não disponíveis.")
