"""
Componente de fila de prioridade — tabela interativa de casos por score.

Exibe os casos mais críticos em ordem decrescente de score.
Cada linha pode ser expandida para revelar o card de detalhe.
"""

import sqlite3
import streamlit as st
import pandas as pd
from typing import Callable, Optional

from core.database import priority_queue


# ---------------------------------------------------------------------------
# Mapeamento de severidade → ícone
# ---------------------------------------------------------------------------

_SEV_ICON = {
    "CRÍTICO":       "🔴",
    "ALTO":          "🟠",
    "MODERADO":      "🟡",
    "BAIXO":         "🟢",
    "MÍNIMO":        "🟢",
    "SEM INDICAÇÃO": "⚪",
}


def render_priority_queue(
    conn: sqlite3.Connection,
    limit: int = 50,
    on_select: Optional[Callable[[str], None]] = None,
    show_patient_hash: bool = False,
) -> None:
    """
    Renderiza a tabela de prioridade.

    Args:
        conn:              Conexão SQLite.
        limit:             Número máximo de casos exibidos.
        on_select:         Callback chamado com analysis_id quando o usuário
                           clica em "Ver detalhe".
        show_patient_hash: Se True exibe a coluna patient_hash (Painel Seguro).
    """
    rows = priority_queue(conn, limit=limit)

    if not rows:
        st.info("Nenhum caso registrado ainda.")
        return

    df = pd.DataFrame(rows)

    # Formatar colunas
    df["Severidade"] = df["severity_level"].map(lambda s: f"{_SEV_ICON.get(s, '')} {s}")
    df["Score"]      = df["score"].map(lambda v: f"{v:.1f}")
    df["Conf."]      = df["confidence"].map(lambda v: f"{v:.0%}")
    df["Analisado"]  = pd.to_datetime(df["analyzed_at"]).dt.strftime("%d/%m/%Y %H:%M")

    display_cols = ["Severidade", "Score", "notification_type", "filename", "Conf.", "Analisado"]
    col_labels   = {
        "notification_type": "Tipo",
        "filename":          "Arquivo",
    }
    if show_patient_hash:
        display_cols.insert(3, "patient_hash")
        col_labels["patient_hash"] = "Paciente (hash)"

    st.markdown(f"**{len(df)} caso(s) priorizados**")

    # Cabeçalho fixo
    header_cols = [1, 1, 2, 2, 1, 1]
    if show_patient_hash:
        header_cols.insert(3, 1)
    if on_select:
        header_cols.append(1)

    h = st.columns(header_cols)
    labels = ["Severidade", "Score", "Tipo", "Arquivo", "Conf.", "Analisado"]
    if show_patient_hash:
        labels.insert(3, "Paciente")
    if on_select:
        labels.append("")
    for col, lbl in zip(h, labels):
        col.markdown(f"**{lbl}**")

    st.markdown("---")

    for _, row in df.iterrows():
        cols = st.columns(header_cols)
        idx = 0
        cols[idx].markdown(row["Severidade"]); idx += 1
        cols[idx].markdown(row["Score"]); idx += 1
        cols[idx].markdown(row["notification_type"]); idx += 1
        if show_patient_hash:
            cols[idx].markdown(f"`{str(row.get('patient_hash',''))[:12]}…`"); idx += 1
        cols[idx].markdown(row["filename"]); idx += 1
        cols[idx].markdown(row["Conf."]); idx += 1
        cols[idx].markdown(row["Analisado"]); idx += 1

        if on_select:
            if cols[idx].button("Ver", key=f"pq_{row['analysis_id']}"):
                on_select(row["analysis_id"])

        st.markdown("---")
