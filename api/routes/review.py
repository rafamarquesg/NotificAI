"""
api/routes/review.py
====================
Endpoints da fila de revisão Human-in-the-Loop.

GET  /review/queue              → Lista tarefas pendentes (Etapa A — UI do técnico)
GET  /review/{task_id}          → Detalhe de uma tarefa
POST /review/{task_id}/validate → Técnico aprova ou rejeita (Etapa B)
GET  /review/stats              → Estatísticas da fila
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hitl.models import AgravoType, ReviewStatus, ValidationDecision

router = APIRouter(prefix="/review", tags=["Revisão HitL"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ValidationRequest(BaseModel):
    """Corpo da Etapa B — decisão do técnico de saúde."""
    decision: ReviewStatus                        # "approved" ou "rejected"
    agravo_confirmed: Optional[AgravoType] = None # Obrigatório se approved
    reviewer_id: str = "tecnico_anonimo"
    notes: Optional[str] = None
    trigger_sinan: bool = False                   # Etapa D: dispara preenchimento SINAN


class ValidationResponse(BaseModel):
    task_id: str
    decision: str
    feedback_record_id: str
    sinan_dispatched: bool
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats", summary="Estatísticas da fila")
def get_stats():
    """Retorna contagens por status para o dashboard do técnico."""
    from ..deps import get_queue
    return get_queue().get_stats()


@router.get("/queue", summary="Fila de revisão pendente")
def get_queue_pending(limit: int = 20):
    """
    **Etapa A do fluxo HitL — visão do técnico.**

    Retorna até `limit` tarefas pendentes ordenadas por severidade (maior primeiro).
    Cada tarefa inclui os trechos destacados vinculados ao paciente.
    """
    from ..deps import get_queue
    tasks = get_queue().get_pending(limit=limit)
    return {"count": len(tasks), "tasks": tasks}


@router.get("/{task_id}", summary="Detalhe de uma tarefa")
def get_task(task_id: str):
    """Retorna todos os campos de uma ReviewTask pelo ID."""
    from ..deps import get_queue
    task = get_queue().get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Tarefa '{task_id}' não encontrada")
    return task


@router.post("/{task_id}/validate", response_model=ValidationResponse, summary="Validar tarefa (Etapa B)")
def validate_task(task_id: str, body: ValidationRequest):
    """
    **Etapa B do fluxo HitL — validação pelo técnico de saúde.**

    - `decision: "approved"` → Confirma que é uma notificação válida.
      Se `trigger_sinan: true`, dispara preenchimento da ficha SINAN (Etapa D).
    - `decision: "rejected"` → Marca como falso positivo.
      O trecho gera um dado rotulado negativo para o modelo ML (Etapa C).

    Em ambos os casos, um FeedbackRecord é gerado automaticamente (Etapa C).
    """
    from ..deps import get_queue, get_feedback_store

    queue = get_queue()
    task = queue.get_by_id(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Tarefa '{task_id}' não encontrada")

    if task["status"] not in (ReviewStatus.PENDING.value, ReviewStatus.IN_REVIEW.value):
        raise HTTPException(
            status_code=409,
            detail=f"Tarefa já processada com status '{task['status']}'",
        )

    if body.decision == ReviewStatus.APPROVED and not body.agravo_confirmed:
        raise HTTPException(
            status_code=422,
            detail="Campo 'agravo_confirmed' é obrigatório quando decision='approved'",
        )

    # Aplica decisão
    decision = ValidationDecision(
        task_id=task_id,
        decision=body.decision,
        agravo_confirmed=body.agravo_confirmed,
        reviewer_id=body.reviewer_id,
        notes=body.notes,
        trigger_sinan=body.trigger_sinan,
    )
    queue.update(task_id, decision)

    # Etapa C — gera feedback record
    text_snippet = " | ".join(
        h.get("evidence_text", "") for h in task.get("highlights", [])
    )
    store = get_feedback_store()
    feedback = store.record(decision, text_snippet=text_snippet, auto_retrain=False)

    return ValidationResponse(
        task_id=task_id,
        decision=body.decision.value,
        feedback_record_id=feedback.record_id,
        sinan_dispatched=body.trigger_sinan and body.decision == ReviewStatus.APPROVED,
        message=(
            "Notificação aprovada. Ficha SINAN será preenchida."
            if body.trigger_sinan and body.decision == ReviewStatus.APPROVED
            else "Decisão registrada e feedback gerado para retreinamento."
        ),
    )
