"""Configuração, enums e exceções do sistema NotificAI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class ProcessingConfig:
    max_file_size_mb: int = 50
    min_text_quality_chars: int = 30
    context_window_chars: int = 150
    max_phrases_per_document: int = 25
    anonymize_identifiers: bool = True
    ocr_dpi: int = 300
    ocr_max_pages: int = 5
    timezone: str = "America/Sao_Paulo"


class ProcessingStatus(Enum):
    SUCCESS = "sucesso"
    PDF_CORRUPTED = "pdf_corrompido"
    OCR_FAILED = "ocr_falhou"
    INSUFFICIENT_TEXT = "texto_insuficiente"
    PROCESSING_ERROR = "erro_processamento"


class QualityLevel(Enum):
    EXCELLENT = "excelente"
    GOOD = "boa"
    FAIR = "regular"
    POOR = "ruim"


class SeverityLevel(Enum):
    CRITICAL = "CRITICO"
    HIGH = "ALTO"
    MODERATE = "MODERADO"
    LOW = "BAIXO"
    MINIMAL = "MINIMO"
    NONE = "SEM INDICACAO"


class DocumentType(Enum):
    EVOLUCAO_MEDICA = "Evolução Médica"
    ANOTACOES_ENFERMAGEM = "Anotações de Enfermagem"
    MULTIPROFISSIONAL = "Multiprofissional"
    OUTROS = "Outros"


class NotificAIError(Exception):
    """Erro base do sistema."""


class PDFProcessingError(NotificAIError):
    """Falha de extração ou validação de PDF."""


class OCRProcessingError(NotificAIError):
    """Falha específica de OCR."""


SEVERITY_THRESHOLDS = {
    SeverityLevel.CRITICAL: 10.0,
    SeverityLevel.HIGH: 6.0,
    SeverityLevel.MODERATE: 3.0,
    SeverityLevel.LOW: 1.0,
    SeverityLevel.MINIMAL: 0.3,
}

CRITICAL_THRESHOLD_MULTIPLIER = 0.7

PATTERN_BONUSES = {
    "chronic_violence": 2.0,
    "escalation_pattern": 1.5,
    "weapons_involved": 3.0,
    "children_present": 2.5,
    "pregnancy_violence": 3.5,
    "sexual_violence": 4.0,
    "death_threats": 3.0,
    "multiple_injuries": 1.5,
    "psychological_control": 2.0,
    "economic_abuse": 1.0,
}
