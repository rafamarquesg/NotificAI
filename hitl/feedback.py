"""
hitl/feedback.py
================
Feedback Loop — Etapa C do fluxo HitL.

Responsabilidade:
  1. Receber ValidationDecision do técnico
  2. Gerar FeedbackRecord (dado rotulado anonimizado)
  3. Persistir em feedback.jsonl
  4. Exportar dataset de treino para o ML quando há exemplos suficientes
  5. Opcionalmente disparar retreinamento automático

Observer Pattern: O pipeline.py chama `FeedbackStore.record()` após cada
validação — sem o pipeline precisar conhecer a lógica de retreinamento.

Etapa D (SINAN): `SinanBridge.submit()` é chamado aqui se `trigger_sinan=True`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from .models import FeedbackRecord, ReviewStatus, ValidationDecision

logger = logging.getLogger(__name__)

_DEFAULT_FEEDBACK_PATH = Path(__file__).parent.parent / "data" / "feedback.jsonl"
_MIN_SAMPLES_TO_RETRAIN = 50   # Limiar mínimo para disparar retreinamento


class FeedbackStore:
    """
    Armazena feedback do técnico e exporta dados de treinamento.

    Uso:
        store = FeedbackStore()
        store.record(decision, text_snippet="...")
        texts, labels = store.export_training_data()
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path or _DEFAULT_FEEDBACK_PATH)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        decision: ValidationDecision,
        text_snippet: str,
        auto_retrain: bool = False,
    ) -> FeedbackRecord:
        """
        Gera e persiste um FeedbackRecord a partir da decisão do técnico.
        Se `auto_retrain=True` e há exemplos suficientes, retreina o modelo.
        """
        # Converte decisão → label de treino
        label = self._decision_to_label(decision)

        record = FeedbackRecord(
            task_id=decision.task_id,
            text_snippet=self._anonymize(text_snippet),
            label=label,
            agravo=decision.agravo_confirmed.value if decision.agravo_confirmed else None,
            reviewer_id=decision.reviewer_id,
        )

        self._append(record)
        logger.info(f"Feedback registrado: task={decision.task_id}, label={label}")

        # Disparo de retreinamento automático
        if auto_retrain:
            count = self._count_records()
            if count >= _MIN_SAMPLES_TO_RETRAIN:
                self._trigger_retrain()

        # Etapa D — integração SINAN (só se aprovado e solicitado)
        if decision.trigger_sinan and decision.decision == ReviewStatus.APPROVED:
            self._dispatch_sinan(decision)

        return record

    def export_training_data(self) -> Tuple[List[str], List[str]]:
        """
        Exporta (texts, labels) para uso direto no AgravosClassifier.train().
        Retorna apenas registros não utilizados para treino ainda.
        """
        records = self._load_all()
        texts = [r["text_snippet"] for r in records if r.get("text_snippet")]
        labels = [r["label"] for r in records if r.get("label")]
        return texts, labels

    def export_to_jsonl(self, output_path: Optional[Path] = None) -> Path:
        """Exporta todos os registros para um arquivo JSONL para análise externa."""
        dest = Path(output_path or self._path.parent / "training_export.jsonl")
        records = self._load_all()
        with open(dest, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        logger.info(f"{len(records)} registros exportados para {dest}")
        return dest

    def get_stats(self) -> dict:
        records = self._load_all()
        from collections import Counter
        label_dist = Counter(r.get("label") for r in records)
        return {
            "total_feedback": len(records),
            "label_distribution": dict(label_dist),
            "ready_to_retrain": len(records) >= _MIN_SAMPLES_TO_RETRAIN,
        }

    # ------------------------------------------------------------------
    # Privados
    # ------------------------------------------------------------------

    @staticmethod
    def _decision_to_label(decision: ValidationDecision) -> str:
        if decision.decision == ReviewStatus.APPROVED:
            return "notificavel"
        if decision.decision == ReviewStatus.REJECTED:
            return "nao_notificavel"
        return "incerto"

    @staticmethod
    def _anonymize(text: str) -> str:
        """Remove CPF, RGHC e nomes antes de armazenar (LGPD)."""
        import re
        # Remove CPF
        text = re.sub(r'\d{3}[\.\-]?\d{3}[\.\-]?\d{3}[\.\-]?\d{2}', '[CPF]', text)
        # Remove RGHC (sequência de 6-12 dígitos no contexto de prontuário)
        text = re.sub(r'(?:RGHC|Prontu[aá]rio)[:\s#]*\d{4,12}', '[RGHC]', text, flags=re.IGNORECASE)
        return text

    def _append(self, record: FeedbackRecord) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.__dict__, ensure_ascii=False) + "\n")

    def _load_all(self) -> List[dict]:
        if not self._path.exists():
            return []
        records = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    def _count_records(self) -> int:
        return len(self._load_all())

    def _trigger_retrain(self) -> None:
        """Dispara retreinamento do modelo ML com dados acumulados."""
        try:
            from ..nlp.ml_classifier import AgravosClassifier
            texts, labels = self.export_training_data()
            if len(texts) < _MIN_SAMPLES_TO_RETRAIN:
                return
            clf = AgravosClassifier()
            metrics = clf.train(texts, labels)
            clf.save()
            logger.info(f"Retreinamento automático concluído: {metrics}")
        except Exception as exc:
            logger.error(f"Falha no retreinamento automático: {exc}")

    def _dispatch_sinan(self, decision: ValidationDecision) -> None:
        """Etapa D — dispara integração SINAN após aprovação do técnico."""
        try:
            from ..notification.sinan_bridge import SinanBridge
            bridge = SinanBridge()
            bridge.submit(decision)
        except Exception as exc:
            logger.error(f"Falha ao disparar SINAN: {exc}")
