"""
Visualizador de linha do tempo do paciente.

Exibe todos os documentos/análises associados a um mesmo patient_hash,
detectando reincidência e mostrando evolução dos scores ao longo do tempo.

Acessível apenas no Painel Seguro (após autenticação).
"""

import sqlite3
import streamlit as st
import pandas as pd
from typing import Optional

from core.database import get_patient_timeline, get_patient


_SEVERITY_ICON = {
    "CRÍTICO":       "🔴",
    "ALTO":          "🟠",
    "MODERADO":      "🟡",
    "BAIXO":         "🟢",
    "MÍNIMO":        "🟢",
    "SEM INDICAÇÃO": "⚪",
}

_STATUS_ICON = {
    "pendente":    "⏳",
    "em análise":  "🔍",
    "notificado":  "✅",
    "arquivado":   "📁",
}


def render_patient_timeline(
    conn: sqlite3.Connection,
    patient_hash: str,
    session_id: Optional[str] = None,
    on_select_analysis: Optional[callable] = None,
) -> None:
    """
    Renderiza a linha do tempo de um paciente.

    Args:
        conn:                 Conexão SQLite.
        patient_hash:         Hash SHA256 do paciente.
        session_id:           Sessão para log de auditoria.
        on_select_analysis:   Callback para abrir detalhe de análise.
    """
    rows = get_patient_timeline(conn, patient_hash)

    if not rows:
        st.info("Nenhum documento registrado para este paciente.")
        return

    # --- Cabeçalho com alerta de reincidência ---
    n_docs = len(rows)
    if n_docs > 1:
        st.error(
            f"⚠️ **Reincidência detectada** — {n_docs} documento(s) associados a este paciente.",
            icon="⚠️",
        )
    else:
        st.success("Primeiro registro para este paciente.")

    # --- Dados do paciente (se disponíveis) ---
    patient = get_patient(conn, patient_hash)
    if patient:
        with st.expander("Identificação do Paciente", expanded=False):
            c1, c2 = st.columns(2)
            c1.markdown(f"**Nome:** {patient.get('nome_paciente') or '—'}")
            c1.markdown(f"**RGHC:** {patient.get('rghc') or '—'}")
            c2.markdown(f"**CPF:** {patient.get('cpf') or '—'}")
            c2.markdown(f"**Nasc.:** {patient.get('data_nascimento') or '—'}")
            st.caption(f"Hash: `{patient_hash}`")

    # --- Gráfico de evolução de score ---
    if n_docs > 1:
        df = pd.DataFrame(rows)
        df["analyzed_at"] = pd.to_datetime(df["analyzed_at"])
        df = df.sort_values("analyzed_at")

        try:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df["analyzed_at"],
                y=df["score"],
                mode="lines+markers",
                marker=dict(size=10, color=df["score"], colorscale="RdYlGn_r", showscale=True),
                text=df["notification_type"],
                hovertemplate="Data: %{x|%d/%m/%Y}<br>Score: %{y:.2f}<br>Tipo: %{text}<extra></extra>",
            ))
            fig.update_layout(
                title="Evolução do Score de Risco",
                xaxis_title="Data",
                yaxis_title="Score",
                margin=dict(t=40, b=40, l=50, r=30),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            pass

    # --- Lista de documentos ---
    st.markdown(f"### {n_docs} Documento(s) na Timeline")

    for i, row in enumerate(rows):
        sev_icon    = _SEVERITY_ICON.get(row["severity_level"], "")
        status_icon = _STATUS_ICON.get(row["case_status"], "")
        doc_date    = row.get("document_date") or row["analyzed_at"][:10]

        with st.expander(
            f"{sev_icon} **{doc_date}** — {row['notification_type']} "
            f"· Score {row['score']:.1f} · {status_icon} {row['case_status']}",
            expanded=(i == 0),
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Score",      f"{row['score']:.2f}")
            c2.metric("Confiança",  f"{row['confidence']:.0%}")
            c3.metric("Páginas",    row.get("page_count") or "—")
            c4.metric("Status",     row["case_status"])

            st.markdown(f"**Arquivo:** `{row['filename']}`")
            st.caption(f"analysis_id: `{row['analysis_id']}`")

            if on_select_analysis:
                if st.button("Ver detalhe completo", key=f"tl_{row['analysis_id']}"):
                    on_select_analysis(row["analysis_id"])
