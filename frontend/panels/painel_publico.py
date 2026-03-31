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
    st.title("NotificAI — Painel Público")
    st.caption(
        "Dados agregados e anônimos sobre notificações de violência e agravos à saúde. "
        "Nenhuma informação de identificação pessoal é exibida neste painel."
    )

    # -----------------------------------------------------------------------
    # Métricas gerais
    # -----------------------------------------------------------------------
    total = count_analyses(conn)
    type_rows     = count_by_type(conn)
    severity_rows = count_by_severity(conn)

    total_docs     = total  # 1 análise doc. completo por doc (page_number IS NULL)
    critical_count = next((r["total"] for r in severity_rows if r["severity_level"] == "CRÍTICO"), 0)
    high_count     = next((r["total"] for r in severity_rows if r["severity_level"] == "ALTO"), 0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total de Documentos Analisados", total_docs)
    m2.metric("Casos Críticos",  critical_count, delta_color="inverse")
    m3.metric("Casos de Risco Alto", high_count, delta_color="inverse")
    m4.metric("Tipos de Notificação", len(type_rows))

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
    freq_label = st.radio("Agrupar por", ["Semana", "Mês"], horizontal=True, label_visibility="collapsed")
    freq = "week" if freq_label == "Semana" else "month"
    time_rows = analyses_over_time(conn, freq=freq)
    fig = line_over_time(time_rows)
    st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Gráficos — linha 3
    # -----------------------------------------------------------------------
    col_terms, col_cat = st.columns(2)

    with col_terms:
        st.markdown("### Termos mais detectados")
        top_n = st.slider("Número de termos", 5, 30, 15, key="pub_top_n")
        term_rows = top_terms(conn, limit=top_n)
        fig = bar_top_terms(term_rows, top_n=top_n)
        st.plotly_chart(fig, use_container_width=True)

    with col_cat:
        st.markdown("### Categorias ao longo do tempo")
        cat_rows = category_over_time(conn)
        fig = stacked_categories_over_time(cat_rows)
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Nota de rodapé
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.caption(
        "NotificAI · Sistema de Apoio à Notificação de Violências (NUVE) · "
        "Os dados exibidos são estritamente agregados e não permitem identificação individual."
    )
