"""
api/routes/analyze.py
=====================
Endpoints de análise de documentos.

POST /analyze/file    → Upload de arquivo (PDF, DOCX, XLSX, imagem, TXT)
POST /analyze/text    → Texto livre direto (string)
GET  /analyze/{id}    → Recupera resultado de análise por ID
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/analyze", tags=["Análise"])


# ---------------------------------------------------------------------------
# Schemas de entrada/saída
# ---------------------------------------------------------------------------

class TextAnalysisRequest(BaseModel):
    text: str
    source_label: str = "texto_livre"
    patient_hint: Optional[str] = None   # Nome/ID do paciente para ajudar o NER


class HighlightDTO(BaseModel):
    patient_id: str
    patient_name: Optional[str]
    evidence_text: str
    term_detected: str
    category: str
    confidence_score: float
    severity: str
    page_number: int


class AnalysisResponseDTO(BaseModel):
    analysis_id: str
    source: str
    patient_primary_id: str
    patient_name: Optional[str]
    severity_level: str
    total_score: float
    ml_label: str
    ml_confidence: float
    review_task_id: Optional[str]   # None se score abaixo do limiar
    highlights: List[HighlightDTO]
    status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/file", response_model=AnalysisResponseDTO, summary="Analisar arquivo")
async def analyze_file(
    file: UploadFile = File(..., description="PDF, DOCX, XLSX, PNG, JPG ou TXT"),
    min_score_threshold: float = Form(
        default=2.0,
        description="Score mínimo para criar tarefa de revisão (0.0 = todas)",
    ),
    auto_queue: bool = Form(
        default=True,
        description="Se True, cria ReviewTask automaticamente se score ≥ limiar",
    ),
):
    """
    **Etapa A do fluxo HitL.**

    Recebe qualquer arquivo suportado, extrai o texto, analisa,
    e retorna os trechos destacados vinculados ao paciente identificado.

    Se `auto_queue=True` e o score atingir o limiar, uma ReviewTask é criada
    automaticamente na fila do técnico.
    """
    # Salva o upload em arquivo temporário
    suffix = Path(file.filename or "upload.pdf").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        return _run_pipeline(
            source=str(file.filename),
            file_path=tmp_path,
            raw_text=None,
            min_score=min_score_threshold,
            auto_queue=auto_queue,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/text", response_model=AnalysisResponseDTO, summary="Analisar texto livre")
def analyze_text(body: TextAnalysisRequest, auto_queue: bool = True):
    """
    **Etapa A do fluxo HitL — entrada via texto.**

    Ideal para integração com sistemas que já fornecem o texto extraído
    (ex: sistemas HIS/RIS com extração própria de PDF).
    """
    return _run_pipeline(
        source=body.source_label,
        file_path=None,
        raw_text=body.text,
        min_score=2.0,
        auto_queue=auto_queue,
    )


@router.get("/{analysis_id}", summary="Recuperar resultado de análise")
def get_analysis(analysis_id: str):
    """Recupera um resultado de análise pelo ID (lookup na fila de revisão)."""
    from ..deps import get_queue
    queue = get_queue()
    task = queue.get_by_id(analysis_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Análise '{analysis_id}' não encontrada")
    return task


# ---------------------------------------------------------------------------
# Lógica central (chama o pipeline)
# ---------------------------------------------------------------------------

def _run_pipeline(
    source: str,
    file_path: Optional[Path],
    raw_text: Optional[str],
    min_score: float,
    auto_queue: bool,
) -> AnalysisResponseDTO:
    from pipeline import NotificAIPipeline
    from ..deps import get_queue

    pipeline = NotificAIPipeline()

    if file_path:
        result = pipeline.run_file(file_path)
    else:
        result = pipeline.run_text(raw_text, source_label=source)

    if result is None:
        raise HTTPException(status_code=422, detail="Falha ao processar o documento")

    # Cria tarefa na fila se score ≥ limiar
    review_task_id = None
    if auto_queue and result.severity_score >= min_score:
        queue = get_queue()
        task = result.to_review_task()
        queue.push(task)
        review_task_id = task.task_id

    # Monta highlights para resposta
    highlights = [
        HighlightDTO(
            patient_id=result.patient_entities.primary_id,
            patient_name=result.patient_entities.nome,
            evidence_text=h.evidence_text,
            term_detected=h.term_detected,
            category=h.category,
            confidence_score=h.confidence_score,
            severity=h.severity,
            page_number=h.page_number,
        )
        for h in result.highlights
    ]

    return AnalysisResponseDTO(
        analysis_id=result.analysis_id,
        source=source,
        patient_primary_id=result.patient_entities.primary_id,
        patient_name=result.patient_entities.nome,
        severity_level=result.severity_level,
        total_score=result.severity_score,
        ml_label=result.ml_label,
        ml_confidence=result.ml_confidence,
        review_task_id=review_task_id,
        highlights=highlights,
        status=result.status,
    )
