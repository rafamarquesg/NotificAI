"""Camada NLP — NotificAI."""

from .ner import PatientNER, PatientEntities
from .negation import NegationHandler, NegationResult
from .ml_classifier import AgravosClassifier, ClassificationResult

__all__ = [
    "PatientNER", "PatientEntities",
    "NegationHandler", "NegationResult",
    "AgravosClassifier", "ClassificationResult",
]
