"""
nlp/ml_classifier.py
====================
Classificador de ML para risco de notificação compulsória.

ARQUITETURA ATUAL (Fase 1 — cold start):
  Pipeline scikit-learn: TF-IDF + Regressão Logística
  Treinado com dados rotulados exportados pelo módulo hitl/feedback.py.

ARQUITETURA FUTURA (Fase 2 — após acúmulo de dados rotulados):
  Substituir pelo fine-tuning de BERTimbau (BERT pré-treinado em PT-BR)
  ou BioBERT adaptado para textos clínicos brasileiros.
  O contrato desta classe (predict / train) permanece idêntico.

Design Pattern: Strategy — o pipeline pode trocar o classificador
sem modificar o orquestrador (pipeline.py).
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = Path(__file__).parent.parent / "data" / "ml_model.pkl"


@dataclass
class ClassificationResult:
    label: str           # "notificavel" | "nao_notificavel" | "incerto"
    confidence: float    # 0.0 → 1.0
    probabilities: dict  # {"notificavel": 0.82, "nao_notificavel": 0.18}
    model_version: str = "tfidf-lr-v1"
    used_fallback: bool = False  # True quando modelo não está treinado ainda


class AgravosClassifier:
    """
    Wrapper do classificador de ML.

    Uso:
        clf = AgravosClassifier()
        result = clf.predict("Paciente com hematoma orbital compatível com agressão")
        print(result.label, result.confidence)

    Para treinar com novos dados rotulados (feedback loop):
        clf.train(texts=["..."], labels=["notificavel", ...])
        clf.save()
    """

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = Path(model_path or _DEFAULT_MODEL_PATH)
        self._pipeline = None
        self._loaded = False
        self._try_load()

    # ------------------------------------------------------------------
    # Inferência
    # ------------------------------------------------------------------

    def predict(self, text: str) -> ClassificationResult:
        """Classifica um texto e retorna label + confiança."""
        if not self._loaded or self._pipeline is None:
            return self._rule_based_fallback(text)

        try:
            proba = self._pipeline.predict_proba([text])[0]
            classes = self._pipeline.classes_
            probs = dict(zip(classes, proba.tolist()))
            best_label = classes[proba.argmax()]
            confidence = float(proba.max())

            # Zona de incerteza: quando confiança < 60%, marca como "incerto"
            if confidence < 0.60:
                best_label = "incerto"

            return ClassificationResult(
                label=best_label,
                confidence=confidence,
                probabilities=probs,
                model_version=self._model_version,
            )
        except Exception as exc:
            logger.warning(f"Erro na predição ML: {exc}. Usando fallback por regras.")
            return self._rule_based_fallback(text)

    def predict_batch(self, texts: List[str]) -> List[ClassificationResult]:
        return [self.predict(t) for t in texts]

    # ------------------------------------------------------------------
    # Treinamento (chamado pelo feedback loop)
    # ------------------------------------------------------------------

    def train(self, texts: List[str], labels: List[str]) -> dict:
        """
        Treina (ou retreina) o pipeline com dados rotulados.
        Retorna métricas de avaliação (cross-validation).
        """
        if len(texts) < 10:
            return {"error": "Mínimo de 10 exemplos rotulados necessários para treinar."}

        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.model_selection import cross_val_score
        import numpy as np

        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                ngram_range=(1, 3),
                max_features=10_000,
                sublinear_tf=True,
                analyzer="word",
            )),
            ("clf", LogisticRegression(
                max_iter=500,
                class_weight="balanced",
                C=1.0,
                solver="lbfgs",
                multi_class="auto",
            )),
        ])

        scores = cross_val_score(pipeline, texts, labels, cv=5, scoring="f1_weighted")
        pipeline.fit(texts, labels)

        self._pipeline = pipeline
        self._loaded = True
        self._model_version = "tfidf-lr-v1"

        metrics = {
            "f1_weighted_mean": float(np.mean(scores)),
            "f1_weighted_std": float(np.std(scores)),
            "n_samples": len(texts),
            "classes": list(set(labels)),
        }
        logger.info(f"Modelo treinado: F1={metrics['f1_weighted_mean']:.3f} ± {metrics['f1_weighted_std']:.3f}")
        return metrics

    def save(self, path: Optional[Path] = None) -> Path:
        """Persiste o modelo treinado em disco."""
        target = Path(path or self.model_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as f:
            pickle.dump({"pipeline": self._pipeline, "version": self._model_version}, f)
        logger.info(f"Modelo salvo em: {target}")
        return target

    # ------------------------------------------------------------------
    # Privados
    # ------------------------------------------------------------------

    def _try_load(self) -> None:
        if not self.model_path.exists():
            logger.info("Modelo ML não encontrado. Usando fallback por regras léxicas.")
            return
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            self._pipeline = data["pipeline"]
            self._model_version = data.get("version", "unknown")
            self._loaded = True
            logger.info(f"Modelo ML carregado: {self._model_version}")
        except Exception as exc:
            logger.warning(f"Falha ao carregar modelo ML: {exc}")

    @staticmethod
    def _rule_based_fallback(text: str) -> ClassificationResult:
        """
        Fallback simples baseado em contagem léxica.
        Usado enquanto o modelo não está treinado.
        Evita que o sistema fique inoperante no cold-start.
        """
        text_lower = text.lower()
        high_risk_terms = [
            "violência", "agressão", "espancamento", "estupro", "maus-tratos",
            "lesão corporal", "ameaça de morte", "feminicídio",
        ]
        hits = sum(1 for t in high_risk_terms if t in text_lower)

        if hits >= 3:
            return ClassificationResult(
                label="notificavel", confidence=0.55,
                probabilities={"notificavel": 0.55, "nao_notificavel": 0.45},
                model_version="rule-fallback", used_fallback=True,
            )
        if hits >= 1:
            return ClassificationResult(
                label="incerto", confidence=0.40,
                probabilities={"notificavel": 0.40, "nao_notificavel": 0.60},
                model_version="rule-fallback", used_fallback=True,
            )
        return ClassificationResult(
            label="nao_notificavel", confidence=0.80,
            probabilities={"notificavel": 0.20, "nao_notificavel": 0.80},
            model_version="rule-fallback", used_fallback=True,
        )

    @property
    def _model_version(self) -> str:
        return getattr(self, "_mv", "rule-fallback")

    @_model_version.setter
    def _model_version(self, v: str) -> None:
        self._mv = v
