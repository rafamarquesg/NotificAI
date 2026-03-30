"""Camada de ingestão multiformato — NotificAI."""

from .base import AbstractExtractor, ExtractionResult
from .router import IngestionRouter

__all__ = ["AbstractExtractor", "ExtractionResult", "IngestionRouter"]
