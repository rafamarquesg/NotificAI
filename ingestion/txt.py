"""
ingestion/txt.py
================
Extrator para texto livre (.txt, .text, .md).
Detecta encoding automaticamente.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .base import AbstractExtractor, ExtractionResult


class TxtExtractor(AbstractExtractor):
    supported_extensions = [".txt", ".text", ".md"]

    def extract(self, file_path: Path) -> ExtractionResult:
        if not file_path.exists():
            return self._build_error_result(file_path, "txt", f"Arquivo não encontrado: {file_path}")

        try:
            text, pages, meta = self._extract(file_path)
            return ExtractionResult(
                text=self._clean_text(text),
                source_path=str(file_path),
                format="txt",
                page_count=1,
                extraction_method="plain-text",
                quality_score=1.0 if len(text) > 30 else 0.2,
                pages=pages,
                metadata=meta,
            )
        except Exception as exc:
            return self._build_error_result(file_path, "txt", str(exc))

    def _extract(self, path: Path) -> Tuple[str, List[Dict], Dict[str, Any]]:
        encoding = self._detect_encoding(path)
        text = path.read_text(encoding=encoding, errors="replace")
        pages = [{"page": 1, "text": text}]
        meta = {
            "encoding": encoding,
            "char_count": len(text),
            "word_count": len(text.split()),
        }
        return text, pages, meta

    @staticmethod
    def _detect_encoding(path: Path) -> str:
        """Tenta detectar encoding; fallback para utf-8."""
        try:
            import chardet
            raw = path.read_bytes()
            detected = chardet.detect(raw)
            return detected.get("encoding") or "utf-8"
        except ImportError:
            # Tenta utf-8, latin-1 em sequência
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    path.read_text(encoding=enc)
                    return enc
                except UnicodeDecodeError:
                    continue
            return "utf-8"
