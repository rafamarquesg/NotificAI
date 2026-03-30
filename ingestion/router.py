"""
ingestion/router.py
===================
Roteador automático de formato (Factory + Registry).

Seleciona o extrator correto pela extensão do arquivo.
Para adicionar um novo formato, basta registrar o extrator em REGISTRY.

Exemplo:
    result = IngestionRouter().route(Path("prontuario.pdf"))
"""

from pathlib import Path
from typing import Dict, Optional, Type

from .base import AbstractExtractor, ExtractionResult
from .pdf import PdfExtractor
from .ocr import OcrExtractor
from .docx import DocxExtractor
from .xlsx import XlsxExtractor
from .txt import TxtExtractor

# Mapeamento extensão → classe extratora
_REGISTRY: Dict[str, Type[AbstractExtractor]] = {}


def _register_all() -> None:
    for cls in [PdfExtractor, OcrExtractor, DocxExtractor, XlsxExtractor, TxtExtractor]:
        for ext in cls.supported_extensions:
            _REGISTRY[ext.lower()] = cls


_register_all()


class IngestionRouter:
    """
    Ponto de entrada único para ingestão de qualquer formato.

    Uso:
        router = IngestionRouter()
        result = router.route(Path("exame.pdf"))
        if result.is_valid:
            process(result.text)
    """

    def route(self, file_path: Path) -> ExtractionResult:
        """Roteia o arquivo ao extrator adequado e retorna ExtractionResult."""
        ext = file_path.suffix.lower()
        extractor_cls = _REGISTRY.get(ext)

        if extractor_cls is None:
            return ExtractionResult(
                text="",
                source_path=str(file_path),
                format="unknown",
                error=f"Formato não suportado: '{ext}'. "
                      f"Formatos aceitos: {sorted(_REGISTRY.keys())}",
            )

        return extractor_cls().extract(file_path)

    def route_text(self, raw_text: str, source_label: str = "texto_livre") -> ExtractionResult:
        """
        Aceita texto livre diretamente (sem arquivo).
        Útil para integração com sistemas que já retornam string.
        """
        from .base import AbstractExtractor
        cleaned = AbstractExtractor._clean_text(raw_text)
        return ExtractionResult(
            text=cleaned,
            source_path=source_label,
            format="txt",
            page_count=1,
            extraction_method="direct-text",
            quality_score=1.0 if len(cleaned) > 30 else 0.2,
            pages=[{"page": 1, "text": cleaned}],
        )

    @staticmethod
    def supported_formats() -> list:
        return sorted(_REGISTRY.keys())
