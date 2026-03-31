"""
Fábricas de gráficos Plotly para os painéis do NotificAI.
"""

from typing import List, Dict, Any
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# ---------------------------------------------------------------------------
# Paleta de cores por tipo de notificação
# ---------------------------------------------------------------------------

_TYPE_COLORS = {
    "Violência Física":              "#e74c3c",
    "Violência Sexual":              "#8e44ad",
    "Violência Psicológica/Moral":   "#e67e22",
    "Violência Autoprovocada":       "#c0392b",
    "Negligência/Abandono":          "#2980b9",
    "Trabalho Infantil":             "#f39c12",
    "Tráfico de Pessoas":            "#16a085",
    "Outros/Não Classificado":       "#7f8c8d",
}

_SEVERITY_COLORS = {
    "CRÍTICO":        "#c0392b",
    "ALTO":           "#e74c3c",
    "MODERADO":       "#e67e22",
    "BAIXO":          "#f1c40f",
    "MÍNIMO":         "#2ecc71",
    "SEM INDICAÇÃO":  "#95a5a6",
}


# ---------------------------------------------------------------------------
# Donut — distribuição por tipo de notificação
# ---------------------------------------------------------------------------

def donut_by_type(rows: List[Dict[str, Any]]) -> go.Figure:
    """Recebe saída de database.count_by_type()."""
    if not rows:
        return _empty_fig("Sem dados de notificações")

    df = pd.DataFrame(rows)
    colors = [_TYPE_COLORS.get(t, "#bdc3c7") for t in df["notification_type"]]

    fig = go.Figure(go.Pie(
        labels=df["notification_type"],
        values=df["total"],
        hole=0.45,
        marker_colors=colors,
        textinfo="percent+label",
        hovertemplate="%{label}<br>%{value} casos (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        title_text="Distribuição por Tipo de Notificação",
        showlegend=False,
        margin=dict(t=50, b=20, l=20, r=20),
    )
    return fig


# ---------------------------------------------------------------------------
# Barras horizontais — distribuição por severidade
# ---------------------------------------------------------------------------

def bar_by_severity(rows: List[Dict[str, Any]]) -> go.Figure:
    """Recebe saída de database.count_by_severity()."""
    if not rows:
        return _empty_fig("Sem dados de severidade")

    order = ["CRÍTICO", "ALTO", "MODERADO", "BAIXO", "MÍNIMO", "SEM INDICAÇÃO"]
    df = pd.DataFrame(rows)
    df["severity_level"] = pd.Categorical(df["severity_level"], categories=order, ordered=True)
    df = df.sort_values("severity_level")
    colors = [_SEVERITY_COLORS.get(s, "#bdc3c7") for s in df["severity_level"]]

    fig = go.Figure(go.Bar(
        x=df["total"],
        y=df["severity_level"],
        orientation="h",
        marker_color=colors,
        text=df["total"],
        textposition="outside",
        hovertemplate="%{y}: %{x} casos<extra></extra>",
    ))
    fig.update_layout(
        title_text="Casos por Severidade",
        xaxis_title="Quantidade",
        yaxis_title="",
        margin=dict(t=50, b=40, l=140, r=60),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#ecf0f1")
    return fig


# ---------------------------------------------------------------------------
# Série temporal — volume de análises por período
# ---------------------------------------------------------------------------

def line_over_time(rows: List[Dict[str, Any]]) -> go.Figure:
    """Recebe saída de database.analyses_over_time()."""
    if not rows:
        return _empty_fig("Sem dados temporais")

    df = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["period"],
        y=df["total"],
        mode="lines+markers",
        name="Casos",
        line=dict(color="#2980b9", width=2),
        marker=dict(size=6),
        hovertemplate="Período: %{x}<br>Casos: %{y}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["period"],
        y=df["avg_score"],
        mode="lines",
        name="Score médio",
        yaxis="y2",
        line=dict(color="#e74c3c", width=1.5, dash="dash"),
        hovertemplate="Período: %{x}<br>Score médio: %{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title_text="Evolução Temporal dos Casos",
        xaxis_title="Período",
        yaxis=dict(title="Nº de Casos"),
        yaxis2=dict(title="Score Médio", overlaying="y", side="right", showgrid=False),
        legend=dict(x=0, y=1.1, orientation="h"),
        margin=dict(t=60, b=50, l=60, r=60),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#ecf0f1", tickangle=-30)
    fig.update_yaxes(showgrid=True, gridcolor="#ecf0f1")
    return fig


# ---------------------------------------------------------------------------
# Barras — top termos detectados
# ---------------------------------------------------------------------------

def bar_top_terms(rows: List[Dict[str, Any]], top_n: int = 15) -> go.Figure:
    """Recebe saída de database.top_terms()."""
    if not rows:
        return _empty_fig("Sem termos detectados")

    df = pd.DataFrame(rows).head(top_n).sort_values("freq")
    fig = go.Figure(go.Bar(
        x=df["freq"],
        y=df["term"],
        orientation="h",
        marker=dict(
            color=df["avg_weight"],
            colorscale="RdYlGn_r",
            showscale=True,
            colorbar=dict(title="Peso"),
        ),
        text=df["freq"],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Frequência: %{x}<br>Peso médio: %{marker.color:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title_text=f"Top {top_n} Termos Detectados",
        xaxis_title="Frequência",
        yaxis_title="",
        margin=dict(t=50, b=40, l=160, r=80),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#ecf0f1")
    return fig


# ---------------------------------------------------------------------------
# Stacked bar — categorias ao longo do tempo
# ---------------------------------------------------------------------------

def stacked_categories_over_time(rows: List[Dict[str, Any]]) -> go.Figure:
    """Recebe saída de database.category_over_time()."""
    if not rows:
        return _empty_fig("Sem dados de categorias")

    df = pd.DataFrame(rows)
    pivot = df.pivot_table(index="period", columns="category", values="total", fill_value=0).reset_index()

    fig = go.Figure()
    for col in pivot.columns[1:]:
        fig.add_trace(go.Bar(
            name=col,
            x=pivot["period"],
            y=pivot[col],
            hovertemplate=f"{col}<br>Período: %{{x}}<br>Detecções: %{{y}}<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack",
        title_text="Categorias de Termos ao Longo do Tempo",
        xaxis_title="Período",
        yaxis_title="Detecções",
        legend=dict(x=1.01, y=1, orientation="v"),
        margin=dict(t=50, b=50, l=60, r=180),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(tickangle=-30)
    return fig


# ---------------------------------------------------------------------------
# Scatter — score por página de um documento
# ---------------------------------------------------------------------------

def scatter_page_scores(rows: List[Dict[str, Any]], filename: str = "") -> go.Figure:
    """Recebe saída de database.get_page_analyses()."""
    if not rows:
        return _empty_fig("Documento sem análise por página")

    df = pd.DataFrame(rows)
    colors = [_TYPE_COLORS.get(t, "#bdc3c7") for t in df["notification_type"]]

    fig = go.Figure(go.Scatter(
        x=df["page_number"],
        y=df["score"],
        mode="markers+lines",
        marker=dict(color=colors, size=10),
        text=df["notification_type"],
        hovertemplate="Página %{x}<br>Score: %{y:.2f}<br>Tipo: %{text}<extra></extra>",
    ))
    fig.update_layout(
        title_text=f"Score por Página — {filename}",
        xaxis_title="Página",
        yaxis_title="Score de Risco",
        margin=dict(t=50, b=50, l=60, r=30),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(dtick=1, showgrid=True, gridcolor="#ecf0f1")
    fig.update_yaxes(showgrid=True, gridcolor="#ecf0f1")
    return fig


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _empty_fig(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color="#7f8c8d"),
    )
    fig.update_layout(
        xaxis_visible=False,
        yaxis_visible=False,
        margin=dict(t=30, b=30, l=30, r=30),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
