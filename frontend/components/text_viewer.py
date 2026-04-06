"""
Visualizador de texto com termos de violência destacados por cor.

Renderiza o texto do prontuário com marcação HTML inline dos termos
detectados, agrupados por categoria (cada categoria tem uma cor distinta).
"""

import re
import sqlite3
from typing import Any, Dict, List, Optional

import streamlit as st

from core.database import get_detections, get_analysis_detail

# Paleta de cores por categoria lexical
_CATEGORY_COLORS: Dict[str, Dict[str, str]] = {
    "medical_formal":        {"bg": "#fadbd8", "border": "#e74c3c", "label": "Médico"},
    "legal_police":          {"bg": "#fdebd0", "border": "#e67e22", "label": "Jurídico"},
    "maria_penha_domestic":  {"bg": "#f9ebea", "border": "#c0392b", "label": "Doméstico"},
    "healthcare_nursing":    {"bg": "#d5f5e3", "border": "#27ae60", "label": "Enfermagem"},
    "colloquial_popular":    {"bg": "#d6eaf8", "border": "#2980b9", "label": "Coloquial"},
    "orthographic_variations": {"bg": "#e8daef", "border": "#8e44ad", "label": "Variação"},
    "psychological_abuse":   {"bg": "#fef9e7", "border": "#f39c12", "label": "Psicológico"},
    "child_specific":        {"bg": "#d1f2eb", "border": "#1abc9c", "label": "Criança"},
}

_DEFAULT_COLOR = {"bg": "#f0f0f0", "border": "#7f8c8d", "label": "Outros"}


def render_text_viewer(
    conn: sqlite3.Connection,
    analysis_id: str,
    max_chars: int = 8000,
) -> None:
    """
    Exibe o texto do prontuário com termos detectados destacados.

    Args:
        conn:        Conexão SQLite.
        analysis_id: ID da análise cujos termos serão destacados.
        max_chars:   Limite de caracteres exibidos (prontuários podem ser longos).
    """
    detail     = get_analysis_detail(conn, analysis_id)
    detections = get_detections(conn, analysis_id)

    if not detail:
        st.warning("Análise não encontrada.")
        return

    # Tentar recuperar texto original do banco (via detecções — contextos)
    # Como não armazenamos o texto completo, reconstruímos a visualização
    # a partir dos contextos e frases detectadas.
    _render_detection_legend(detections)
    st.markdown("---")

    if not detections:
        st.info("Nenhum termo de violência detectado neste documento.")
        _render_document_meta(detail)
        return

    _render_document_meta(detail)
    st.markdown("---")
    _render_detection_cards(detections, max_chars)


def render_text_with_highlights(
    text: str,
    detections: List[Dict[str, Any]],
    max_chars: int = 8000,
) -> None:
    """
    Versão que recebe o texto bruto e a lista de detecções diretamente.
    Usada quando o texto está disponível em memória (ex: análise ao vivo).
    """
    if not text:
        st.info("Texto não disponível para visualização.")
        return

    display_text = text[:max_chars]
    truncated = len(text) > max_chars

    if truncated:
        st.caption(f"Exibindo os primeiros {max_chars:,} de {len(text):,} caracteres.")

    highlighted = _apply_highlights(display_text, detections)
    _render_legend_from_detections(detections)
    st.markdown(
        f"""
        <div style="
            background:#fafafa;
            border:1px solid #e0e0e0;
            border-radius:8px;
            padding:16px;
            font-family:'Courier New',monospace;
            font-size:0.85rem;
            line-height:1.7;
            max-height:500px;
            overflow-y:auto;
            white-space:pre-wrap;
            word-break:break-word;
        ">{highlighted}</div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Internos
# ---------------------------------------------------------------------------

def _apply_highlights(text: str, detections: List[Dict[str, Any]]) -> str:
    """Aplica marcação HTML nos spans detectados (sem sobreposição)."""
    if not detections:
        return _escape_html(text)

    # Ordenar por posição inicial
    spans = sorted(
        [
            (
                d["position_start"],
                d["position_end"],
                d["category"],
                d["term"],
                d.get("negated", False),
            )
            for d in detections
            if "position_start" in d and "position_end" in d
        ],
        key=lambda x: x[0],
    )

    result = []
    cursor = 0

    for start, end, category, term, negated in spans:
        if start < cursor:
            continue  # sobreposição — pular
        # Texto antes do match
        result.append(_escape_html(text[cursor:start]))
        # Match destacado
        colors = _CATEGORY_COLORS.get(category, _DEFAULT_COLOR)
        if negated:
            # Termos negados em cinza com tachado
            result.append(
                f'<mark style="background:#ecf0f1;border-bottom:2px dashed #95a5a6;'
                f'padding:1px 3px;border-radius:3px;text-decoration:line-through;'
                f'color:#7f8c8d;" title="Negado: {_escape_html(term)}">'
                f'{_escape_html(text[start:end])}</mark>'
            )
        else:
            result.append(
                f'<mark style="background:{colors["bg"]};'
                f'border-bottom:2px solid {colors["border"]};'
                f'padding:1px 3px;border-radius:3px;" '
                f'title="{colors["label"]}: {_escape_html(term)}">'
                f'{_escape_html(text[start:end])}</mark>'
            )
        cursor = end

    result.append(_escape_html(text[cursor:]))
    return "".join(result)


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def _render_detection_legend(detections: List[Dict]) -> None:
    """Legenda de categorias presentes nesta análise."""
    if not detections:
        return
    cats = {d["category"] for d in detections if not d.get("negated")}
    if not cats:
        return

    items = []
    for cat in sorted(cats):
        cfg = _CATEGORY_COLORS.get(cat, _DEFAULT_COLOR)
        items.append(
            f'<span style="background:{cfg["bg"]};border:1px solid {cfg["border"]};'
            f'padding:2px 8px;border-radius:12px;font-size:0.78rem;margin:2px;">'
            f'{cfg["label"]}</span>'
        )

    negated_any = any(d.get("negated") for d in detections)
    if negated_any:
        items.append(
            '<span style="background:#ecf0f1;border:1px dashed #95a5a6;'
            'padding:2px 8px;border-radius:12px;font-size:0.78rem;margin:2px;'
            'text-decoration:line-through;color:#7f8c8d;">Negado</span>'
        )

    st.markdown(
        "<div style='margin-bottom:4px;'><strong>Categorias detectadas: </strong>"
        + " ".join(items)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_legend_from_detections(detections: List[Dict[str, Any]]) -> None:
    """Versão para uso com texto bruto (sem DB)."""
    cats = {d.get("category") for d in detections if not d.get("negated")}
    _render_detection_legend([{"category": c, "negated": False} for c in cats if c])


def _render_document_meta(detail: Dict) -> None:
    """Exibe metadados do documento."""
    cols = st.columns(4)
    cols[0].metric("Tipo de Documento", detail.get("document_type") or "—")
    cols[1].metric("Páginas", detail.get("page_count") or "—")
    cols[2].metric("Data do Documento", _fmt_date(detail.get("document_date")))
    cols[3].metric("Extração", detail.get("extraction_method") or "—")


def _render_detection_cards(detections: List[Dict], max_chars: int) -> None:
    """Exibe cada detecção em um card com contexto e frase completa."""
    st.markdown("### Trechos detectados")
    st.caption(
        "Cada trecho abaixo mostra o contexto ao redor do termo identificado pela IA. "
        "Termos riscados estão negados no texto original."
    )

    active   = [d for d in detections if not d.get("negated")]
    negated  = [d for d in detections if d.get("negated")]

    for det in active:
        _render_single_detection(det, negated=False)

    if negated:
        with st.expander(f"Termos negados ({len(negated)}) — provável ausência de violência"):
            for det in negated:
                _render_single_detection(det, negated=True)


def _render_single_detection(det: Dict, negated: bool) -> None:
    cat    = det.get("category", "")
    term   = det.get("term", "")
    weight = det.get("weight", 0.0)
    ctx    = det.get("context_phrase") or det.get("context") or ""
    sent   = det.get("sentence") or ""

    cfg    = _CATEGORY_COLORS.get(cat, _DEFAULT_COLOR)
    color  = "#95a5a6" if negated else cfg["border"]
    label  = cfg["label"]
    alpha  = "66" if negated else ""

    # Destacar o termo no contexto
    if ctx and term:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        ctx_html = pattern.sub(
            lambda m: f'<strong style="color:{color};">{m.group(0)}</strong>',
            _escape_html(ctx),
        )
    else:
        ctx_html = _escape_html(ctx or sent or "—")

    decoration = "text-decoration:line-through;color:#7f8c8d;" if negated else ""

    st.markdown(
        f"""
        <div style="
            border-left:4px solid {color}{alpha};
            background:{cfg['bg'] if not negated else '#f8f9fa'};
            border-radius:0 8px 8px 0;
            padding:10px 14px;
            margin-bottom:10px;
        ">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="
                    background:{color}{alpha};
                    color:{'#fff' if not negated else '#7f8c8d'};
                    padding:2px 8px;
                    border-radius:12px;
                    font-size:0.75rem;
                    font-weight:600;
                ">{label}</span>
                <span style="color:#7f8c8d;font-size:0.75rem;">peso {weight:.1f}</span>
            </div>
            <div style="font-family:monospace;font-size:0.85rem;line-height:1.6;{decoration}">
                …{ctx_html}…
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso[:10]).strftime("%d/%m/%Y")
    except Exception:
        return iso[:10]
