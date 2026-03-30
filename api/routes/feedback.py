"""
api/routes/feedback.py
======================
Endpoints de feedback e retreinamento do modelo ML.

GET  /feedback/stats        → Estatísticas dos dados rotulados
POST /feedback/retrain      → Dispara retreinamento manual do modelo
GET  /feedback/export       → Exporta dataset de treino (JSONL)
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/feedback", tags=["Feedback & ML"])


class RetrainResponse(BaseModel):
    status: str
    metrics: dict
    model_saved: bool


@router.get("/stats", summary="Estatísticas do feedback loop")
def get_feedback_stats():
    """
    Retorna quantos registros rotulados existem e se há dados suficientes
    para disparar retreinamento.
    """
    from ..deps import get_feedback_store
    return get_feedback_store().get_stats()


@router.post("/retrain", response_model=RetrainResponse, summary="Retreinar modelo ML")
def trigger_retrain(background_tasks: BackgroundTasks):
    """
    **Etapa C — Retreinamento manual.**

    Treina o classificador ML com todos os feedbacks acumulados.
    Executado em background para não bloquear a API.

    Requer mínimo de 50 registros rotulados.
    """
    from ..deps import get_feedback_store
    from nlp.ml_classifier import AgravosClassifier

    store = get_feedback_store()
    stats = store.get_stats()

    if not stats["ready_to_retrain"]:
        raise HTTPException(
            status_code=428,
            detail=f"Feedbacks insuficientes: {stats['total_feedback']} registros "
                   f"(mínimo 50 necessários para retreinamento).",
        )

    texts, labels = store.export_training_data()

    def _retrain_job():
        clf = AgravosClassifier()
        metrics = clf.train(texts, labels)
        clf.save()
        return metrics

    background_tasks.add_task(_retrain_job)

    return RetrainResponse(
        status="retreinamento_iniciado",
        metrics={"n_samples": len(texts), "note": "Processando em background"},
        model_saved=False,
    )


@router.get("/export", summary="Exportar dataset de treino")
def export_training_data():
    """
    Exporta todos os registros de feedback como arquivo JSONL.
    Útil para análise externa, auditoria ou importação em outras ferramentas
    (ex: Label Studio, Prodigy).

    Dados são anonimizados (CPF e RGHC removidos) antes da exportação.
    """
    from ..deps import get_feedback_store
    from pathlib import Path

    store = get_feedback_store()
    export_path = store.export_to_jsonl()

    if not export_path.exists():
        raise HTTPException(status_code=404, detail="Nenhum dado de feedback disponível.")

    return FileResponse(
        path=str(export_path),
        media_type="application/x-ndjson",
        filename="notificai_training_data.jsonl",
    )
