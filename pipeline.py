"""
pipeline.py
===========
Orquestrador principal — NotificAI.

Implementa o Chain of Responsibility completo:
  [Ingestão] → [NER] → [Detecção Léxica] → [Negação] → [ML] → [Scoring] → [Highlights]

Uso standalone (sem API):
    pipeline = NotificAIPipeline()
    result = pipeline.run_file(Path("prontuario.pdf"))
    print(result.patient_entities.primary_id, result.severity_level)

Uso via API (api/routes/analyze.py chama este módulo).
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resultado intermediário / output do pipeline
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    """
    Saída completa do pipeline para um documento.
    Vincula paciente + agravos detectados + scores + highlights.
    """
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    patient_entities: Any = None          # PatientEntities
    severity_level: str = "SEM INDICAÇÃO"
    severity_score: float = 0.0
    ml_label: str = "incerto"
    ml_confidence: float = 0.0
    highlights: List[Any] = field(default_factory=list)   # List[DetectionHighlight]
    detections_count: int = 0
    processing_time_ms: int = 0
    status: str = "success"
    error: Optional[str] = None

    def to_review_task(self) -> Any:
        """Converte o resultado em ReviewTask para a fila HitL."""
        from hitl.models import ReviewTask, AgravoType, DetectionHighlight as DH

        return ReviewTask(
            analysis_id=self.analysis_id,
            source_file=self.source,
            patient_primary_id=self.patient_entities.primary_id if self.patient_entities else "?",
            patient_name=self.patient_entities.nome if self.patient_entities else None,
            suspected_agravo=AgravoType.OUTRO,
            severity_score=self.severity_score,
            ml_confidence=self.ml_confidence,
            ml_label=self.ml_label,
            highlights=self.highlights,
        )


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

class NotificAIPipeline:
    """
    Orquestrador que encadeia todos os módulos do sistema.

    Parâmetros:
        score_threshold: Score mínimo para considerar o documento como suspeito
        max_highlights: Máximo de trechos destacados por documento
        use_ml: Se False, usa apenas regras léxicas (útil no cold-start)
    """

    def __init__(
        self,
        score_threshold: float = 2.0,
        max_highlights: int = 15,
        use_ml: bool = True,
    ):
        self.score_threshold = score_threshold
        self.max_highlights = max_highlights

        # Inicialização lazy dos módulos (evita imports desnecessários)
        self._router = None
        self._ner = None
        self._negation = None
        self._lexicon = None
        self._classifier = None

        if use_ml:
            self._init_classifier()

    # ------------------------------------------------------------------
    # Pontos de entrada públicos
    # ------------------------------------------------------------------

    def run_file(self, file_path: Path) -> PipelineResult:
        """Processa um arquivo de qualquer formato suportado."""
        t0 = time.monotonic()
        try:
            extraction = self._get_router().route(file_path)
            if not extraction.is_valid:
                return self._error_result(str(file_path), extraction.error or "Extração falhou")
            return self._process(extraction.text, source=str(file_path), t0=t0)
        except Exception as exc:
            logger.exception(f"Erro no pipeline para {file_path}: {exc}")
            return self._error_result(str(file_path), str(exc))

    def run_text(self, text: str, source_label: str = "texto_livre") -> PipelineResult:
        """Processa texto livre diretamente."""
        t0 = time.monotonic()
        try:
            extraction = self._get_router().route_text(text, source_label)
            return self._process(extraction.text, source=source_label, t0=t0)
        except Exception as exc:
            logger.exception(f"Erro no pipeline para {source_label}: {exc}")
            return self._error_result(source_label, str(exc))

    def run_batch(self, file_paths: List[Path]) -> List[PipelineResult]:
        """Processa múltiplos arquivos em sequência."""
        return [self.run_file(p) for p in file_paths]

    # ------------------------------------------------------------------
    # Cadeia de processamento interna
    # ------------------------------------------------------------------

    def _process(self, text: str, source: str, t0: float) -> PipelineResult:
        # Passo 1: NER — extrai identificadores do paciente
        patient_entities = self._get_ner().extract(text)

        # Passo 2: Detecção léxica hierárquica
        raw_detections = self._get_lexicon().detect(text)

        # Passo 3: Filtro de negação (remove falsos positivos)
        valid_detections = [
            d for d in raw_detections
            if not self._get_negation().check(text, d["pos_start"], d["pos_end"]).is_negated
        ]

        # Passo 4: Scoring e classificação de severidade
        total_score = sum(d["score"] for d in valid_detections)
        severity_level = self._classify_severity(total_score)

        # Passo 5: Classificador ML (complementa o score léxico)
        ml_label, ml_confidence = "incerto", 0.0
        if self._classifier and valid_detections:
            ml_result = self._classifier.predict(text[:3000])
            ml_label = ml_result.label
            ml_confidence = ml_result.confidence

        # Passo 6: Monta highlights para UX (Etapa A)
        highlights = self._build_highlights(
            valid_detections, patient_entities, text
        )

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        return PipelineResult(
            source=source,
            patient_entities=patient_entities,
            severity_level=severity_level,
            severity_score=round(total_score, 2),
            ml_label=ml_label,
            ml_confidence=round(ml_confidence, 3),
            highlights=highlights[: self.max_highlights],
            detections_count=len(valid_detections),
            processing_time_ms=elapsed_ms,
            status="success",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_highlights(
        self, detections: list, patient_entities: Any, text: str
    ) -> list:
        """
        Constrói DetectionHighlight para cada detecção válida.
        Ordena por score decrescente (maior evidência primeiro para o técnico).
        """
        from hitl.models import DetectionHighlight

        highlights = []
        for d in sorted(detections, key=lambda x: x["score"], reverse=True):
            ctx_start = max(0, d["pos_start"] - 120)
            ctx_end = min(len(text), d["pos_end"] + 120)
            evidence = text[ctx_start:ctx_end].strip()

            highlights.append(DetectionHighlight(
                patient_id=patient_entities.primary_id,
                patient_name=patient_entities.nome,
                evidence_text=evidence,
                term_detected=d["term"],
                category=d["category"],
                confidence_score=min(d["score"] / 3.0, 1.0),
                severity=self._classify_severity(d["score"]),
                page_number=d.get("page", 0),
                position_start=d["pos_start"],
                position_end=d["pos_end"],
            ))

        return highlights

    @staticmethod
    def _classify_severity(score: float) -> str:
        if score >= 8.0:
            return "CRÍTICO"
        if score >= 5.0:
            return "ALTO"
        if score >= 3.0:
            return "MODERADO"
        if score >= 1.5:
            return "BAIXO"
        if score > 0:
            return "MÍNIMO"
        return "SEM INDICAÇÃO"

    @staticmethod
    def _error_result(source: str, error: str) -> PipelineResult:
        return PipelineResult(source=source, status="error", error=error)

    # ------------------------------------------------------------------
    # Inicialização lazy dos módulos
    # ------------------------------------------------------------------

    def _get_router(self):
        if self._router is None:
            from ingestion.router import IngestionRouter
            self._router = IngestionRouter()
        return self._router

    def _get_ner(self):
        if self._ner is None:
            from nlp.ner import PatientNER
            self._ner = PatientNER()
        return self._ner

    def _get_negation(self):
        if self._negation is None:
            from nlp.negation import NegationHandler
            self._negation = NegationHandler()
        return self._negation

    def _get_lexicon(self):
        if self._lexicon is None:
            self._lexicon = _LexiconDetector()
        return self._lexicon

    def _init_classifier(self):
        try:
            from nlp.ml_classifier import AgravosClassifier
            self._classifier = AgravosClassifier()
        except Exception as exc:
            logger.warning(f"Classificador ML não disponível: {exc}")
            self._classifier = None


# ---------------------------------------------------------------------------
# Adaptador do léxico existente (complete.py → interface do pipeline)
# ---------------------------------------------------------------------------

class _LexiconDetector:
    """
    Adapta a lógica de detecção do complete.py para a interface do pipeline.
    Retorna dicts padronizados com pos_start, pos_end, score, term, category.
    """

    def __init__(self):
        self._compiled = self._build_patterns()

    def detect(self, text: str) -> List[dict]:
        results = []
        for category, data in self._compiled.items():
            for match in data["pattern"].finditer(text):
                term = match.group(2) if match.lastindex and match.lastindex >= 2 else match.group()
                results.append({
                    "term": term,
                    "category": category,
                    "score": data["weight"],
                    "pos_start": match.start(2) if match.lastindex and match.lastindex >= 2 else match.start(),
                    "pos_end": match.end(2) if match.lastindex and match.lastindex >= 2 else match.end(),
                    "page": 0,
                })
        return results

    @staticmethod
    def _build_patterns() -> Dict[str, Any]:
        """Importa o léxico existente e compila os padrões."""
        try:
            from lexicon import get_lexicon
            lexicon = get_lexicon()
        except ImportError:
            lexicon = _FALLBACK_LEXICON

        compiled: Dict[str, Any] = {}
        for category, data in lexicon.items():
            terms_escaped = [re.escape(t) for t in data["terms"]]
            combined = "|".join(terms_escaped)
            pattern = re.compile(
                rf'(.{{0,0}})({combined})(.{{0,0}})',
                re.IGNORECASE | re.DOTALL,
            )
            compiled[category] = {"pattern": pattern, "weight": data["weight"]}
        return compiled


# Léxico mínimo de fallback (caso lexicon.py não esteja disponível)
_FALLBACK_LEXICON = {
    "medical_formal": {
        "weight": 2.8,
        "terms": ["violência", "agressão", "lesão corporal", "trauma contundente", "estupro"],
    },
    "legal_police": {
        "weight": 2.5,
        "terms": ["feminicídio", "ameaça de morte", "lesão corporal grave"],
    },
}
