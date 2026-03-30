"""
hitl/models.py
==============
Modelos de dados do fluxo Human-in-the-Loop.

Fluxo de estados de um ReviewTask:
  PENDING → IN_REVIEW → APPROVED | REJECTED | DEFERRED

Estes modelos são independentes dos modelos de análise (models.py).
Conversam com eles apenas pelo campo `analysis_id`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"      # Técnico confirmou: é notificável
    REJECTED = "rejected"      # Técnico rejeitou: falso positivo
    DEFERRED = "deferred"      # Técnico adiou: aguardando mais informações


class AgravoType(str, Enum):
    """Tipos de agravo de notificação compulsória (SINAN — Lista Nacional)."""
    VIOLENCIA_DOMESTICA = "Violência Doméstica/Familiar"
    VIOLENCIA_SEXUAL = "Violência Sexual"
    VIOLENCIA_AUTOPROVOCADA = "Violência Autoprovocada / Tentativa de Suicídio"
    MAUS_TRATOS_CRIANCA = "Maus-Tratos contra Criança/Adolescente"
    MAUS_TRATOS_IDOSO = "Maus-Tratos contra Idoso"
    FEMINICIDIO = "Feminicídio / Tentativa"
    NEGLIGENCIA = "Negligência/Abandono"
    OUTRO = "Outro / A Classificar"


@dataclass
class DetectionHighlight:
    """
    Trecho de evidência vinculado a um paciente para exibição ao técnico.
    É o objeto central da UX — o técnico vê exatamente ISTO.
    """
    patient_id: str             # primary_id do PatientEntities
    patient_name: Optional[str]
    evidence_text: str          # Trecho destacado (context_phrase)
    term_detected: str          # Termo léxico que disparou
    category: str               # Categoria (medical_formal, legal_police, etc.)
    confidence_score: float     # 0.0 → 1.0
    severity: str               # SeverityLevel.value
    page_number: int
    position_start: int
    position_end: int


@dataclass
class ReviewTask:
    """
    Tarefa de revisão na fila do técnico de saúde.
    Criada automaticamente pelo pipeline após análise com score ≥ limiar.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    analysis_id: str = ""           # Referência ao AnalysisResult
    source_file: str = ""
    patient_primary_id: str = ""
    patient_name: Optional[str] = None
    suspected_agravo: AgravoType = AgravoType.OUTRO
    severity_score: float = 0.0
    ml_confidence: float = 0.0
    ml_label: str = "incerto"
    highlights: List[DetectionHighlight] = field(default_factory=list)
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    reviewed_at: Optional[str] = None
    reviewer_id: Optional[str] = None   # ID do técnico (para auditoria)
    reviewer_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "analysis_id": self.analysis_id,
            "source_file": self.source_file,
            "patient_primary_id": self.patient_primary_id,
            "patient_name": self.patient_name,
            "suspected_agravo": self.suspected_agravo.value,
            "severity_score": self.severity_score,
            "ml_confidence": self.ml_confidence,
            "ml_label": self.ml_label,
            "highlights": [h.__dict__ for h in self.highlights],
            "status": self.status.value,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "reviewer_id": self.reviewer_id,
            "reviewer_notes": self.reviewer_notes,
        }


@dataclass
class ValidationDecision:
    """
    Decisão do técnico de saúde para uma ReviewTask.
    Etapa B do fluxo HitL.
    """
    task_id: str
    decision: ReviewStatus          # APPROVED ou REJECTED
    agravo_confirmed: Optional[AgravoType] = None  # Se aprovado, qual agravo
    reviewer_id: str = "tecnico_anonimo"
    notes: Optional[str] = None
    trigger_sinan: bool = False     # Se True → dispara preenchimento SINAN (Etapa D)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class FeedbackRecord:
    """
    Registro de feedback gerado a partir de uma ValidationDecision.
    Alimenta o retreinamento contínuo do modelo ML (Etapa C).
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    text_snippet: str = ""          # Trecho de texto (anonymizado)
    label: str = ""                 # "notificavel" | "nao_notificavel"
    agravo: Optional[str] = None
    reviewer_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    used_for_training: bool = False
    model_version_trained: Optional[str] = None
