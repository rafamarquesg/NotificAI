"""
Painel Público — estatísticas agregadas e anônimas.

Não exibe nenhum dado de identificação de paciente.
Destinado a profissionais de saúde pública, gestores e pesquisadores.
"""

import sqlite3
import streamlit as st

from core.database import (
    count_analyses,
    count_by_type,
    count_by_severity,
    analyses_over_time,
    top_terms,
    category_over_time,
    count_period_comparison,
    count_by_status,
    CASE_STATUSES,
)
from components.charts import (
    donut_by_type,
    bar_by_severity,
    line_over_time,
    bar_top_terms,
    stacked_categories_over_time,
)
from components.upload_widget import render_upload_section, render_folder_monitor_section


def render(conn: sqlite3.Connection) -> None:
    """Renderiza o Painel Público completo."""
    st.markdown("""
    <div style="margin-bottom:20px;">
        <div style="color:#F1F5F9;font-size:1.4rem;font-weight:700;margin-bottom:4px;">
            Painel de Vigilância
        </div>
        <div style="color:#4B5563;font-size:0.83rem;">
            Dados agregados e anônimos · Nenhum dado pessoal é exibido neste painel
        </div>
    </div>
    """, unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Métricas gerais com comparação de período
    # -----------------------------------------------------------------------
    freq_metric = st.radio(
        "Período de comparação", ["Semana", "Mês"], horizontal=True, key="pub_freq_metric"
    )
    freq = "week" if freq_metric == "Semana" else "month"

    total         = count_analyses(conn)
    type_rows     = count_by_type(conn)
    severity_rows = count_by_severity(conn)
    period_cmp    = count_period_comparison(conn, freq=freq)
    status_counts = {r["case_status"]: r["total"] for r in count_by_status(conn)}

    critical_count = next((r["total"] for r in severity_rows if r["severity_level"] == "CRÍTICO"), 0)
    high_count     = next((r["total"] for r in severity_rows if r["severity_level"] == "ALTO"), 0)
    pending_count  = status_counts.get("pendente", 0)

    # Linha 1 de métricas: volume e comparação
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        f"Casos ({freq_metric} atual)",
        period_cmp["current"],
        delta=_delta_label(period_cmp),
        delta_color="inverse",
        help=f"Período anterior: {period_cmp['previous']} casos",
    )
    m2.metric("Total Analisado", total)
    m3.metric("Casos Críticos",      critical_count, delta_color="inverse")
    m4.metric("Casos de Risco Alto", high_count,     delta_color="inverse")

    # Linha 2 de métricas: workflow
    st.markdown("")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("⏳ Pendentes",    status_counts.get("pendente",    0))
    s2.metric("🔍 Em análise",   status_counts.get("em análise",  0))
    s3.metric("✅ Notificados",   status_counts.get("notificado",  0))
    s4.metric("📁 Arquivados",    status_counts.get("arquivado",   0))

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Upload / Monitoramento
    # -----------------------------------------------------------------------
    with st.expander("📂 Inserir Documentos", expanded=False):
        tab_upload, tab_folder = st.tabs(["Upload Manual", "Monitoramento de Pasta"])
        with tab_upload:
            render_upload_section(conn)
        with tab_folder:
            render_folder_monitor_section(conn)

    st.markdown("---")

    # -----------------------------------------------------------------------
    # Gráficos — linha 1
    # -----------------------------------------------------------------------
    col_donut, col_severity = st.columns(2)

    with col_donut:
        fig = donut_by_type(type_rows)
        st.plotly_chart(fig, use_container_width=True)

    with col_severity:
        fig = bar_by_severity(severity_rows)
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Gráficos — série temporal
    # -----------------------------------------------------------------------
    st.markdown("### Evolução Temporal")
    freq_label = st.radio("Agrupar por", ["Semana", "Mês"], horizontal=True, key="pub_freq_chart")
    freq_chart = "week" if freq_label == "Semana" else "month"
    time_rows  = analyses_over_time(conn, freq=freq_chart)
    fig        = line_over_time(time_rows)
    st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Gráficos — linha 3
    # -----------------------------------------------------------------------
    col_terms, col_cat = st.columns(2)

    with col_terms:
        st.markdown("### Termos mais detectados")
        top_n     = st.slider("Número de termos", 5, 30, 15, key="pub_top_n")
        term_rows = top_terms(conn, limit=top_n)
        fig       = bar_top_terms(term_rows, top_n=top_n)
        st.plotly_chart(fig, use_container_width=True)

    with col_cat:
        st.markdown("### Categorias ao longo do tempo")
        cat_rows = category_over_time(conn)
        fig      = stacked_categories_over_time(cat_rows)
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Rodapé
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.caption(
        "NotificAI · Sistema de Apoio à Notificação de Violências (NUVE) · "
        "Os dados exibidos são estritamente agregados e não permitem identificação individual."
    )


def _delta_label(cmp: dict) -> str | None:
    """Formata o delta de período para exibição."""
    if cmp["delta_pct"] is None:
        return None
    sign = "+" if cmp["delta_abs"] >= 0 else ""
    return f"{sign}{cmp['delta_abs']} ({sign}{cmp['delta_pct']:.0f}%)"
