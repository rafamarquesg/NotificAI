"""
ingestion/base.py
=================
Contrato abstrato para todos os extratores de formato (Strategy Pattern).

Qualquer novo formato (ex: DICOM, HL7) deve herdar AbstractExtractor
e implementar apenas `extract()`. O resto do pipeline não muda.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ExtractionResult:
    """
    Resultado normalizado de qualquer extrator.
    O pipeline downstream sempre recebe este contrato — independente do formato.
    """
    text: str                          # Texto limpo e padronizado
    source_path: str                   # Caminho original do arquivo
    format: str                        # "pdf", "docx", "xlsx", "txt", "ocr", "image"
    page_count: int = 1
    extraction_method: str = "unknown"
    quality_score: float = 1.0        # 0.0 (ruim) → 1.0 (excelente)
    pages: List[Dict[str, Any]] = field(default_factory=list)  # [{page: N, text: "..."}]
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return bool(self.text and len(self.text.strip()) >= 30 and self.error is None)


class AbstractExtractor(ABC):
    """
    Classe base para todos os extratores (Strategy Pattern).

    Uso:
        extractor = PdfExtractor()
        result: ExtractionResult = extractor.extract(Path("prontuario.pdf"))
    """

    # Extensões que este extrator aceita (para registro automático no router)
    supported_extensions: List[str] = []

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractionResult:
        """
        Extrai texto de `file_path` e retorna um ExtractionResult normalizado.
        Nunca deve lançar exceção — erros vão para `result.error`.
        """

    def _build_error_result(self, file_path: Path, fmt: str, error: str) -> ExtractionResult:
        return ExtractionResult(
            text="",
            source_path=str(file_path),
            format=fmt,
            error=error,
        )

    @staticmethod
    def _clean_text(raw: str) -> str:
        """Normalização básica comum a todos os extratores."""
        import re
        # Remove linhas vazias excessivas
        text = re.sub(r'\n{3,}', '\n\n', raw)
        # Remove espaços múltiplos
        text = re.sub(r'[ \t]{2,}', ' ', text)
        return text.strip()
