"""
ingestion/pdf.py
================
Extrator de PDF com fallback em cadeia:
  1. pdfplumber  (melhor para PDFs nativos/digitados)
  2. PyMuPDF     (fitz — mais rápido, bom para PDFs mistos)
  3. OCR         (fallback para PDFs escaneados — delega ao OcrExtractor)
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .base import AbstractExtractor, ExtractionResult


class PdfExtractor(AbstractExtractor):
    supported_extensions = [".pdf"]

    def extract(self, file_path: Path) -> ExtractionResult:
        if not file_path.exists():
            return self._build_error_result(file_path, "pdf", f"Arquivo não encontrado: {file_path}")

        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 50:
            return self._build_error_result(file_path, "pdf", f"Arquivo muito grande: {file_size_mb:.1f}MB (máx 50MB)")

        # Cadeia de extração
        for method_name, method in self._extraction_chain():
            try:
                text, pages, meta = method(file_path)
                if text and len(text.strip()) >= 30:
                    quality = self._assess_quality(text)
                    return ExtractionResult(
                        text=self._clean_text(text),
                        source_path=str(file_path),
                        format="pdf",
                        page_count=meta.get("page_count", len(pages)),
                        extraction_method=method_name,
                        quality_score=quality,
                        pages=pages,
                        metadata=meta,
                    )
            except Exception as exc:
                continue  # tenta próximo método

        # Todos falharam → delega ao OCR
        from .ocr import OcrExtractor
        ocr = OcrExtractor()
        result = ocr.extract(file_path)
        if result.is_valid:
            return result

        return self._build_error_result(file_path, "pdf", "Todos os métodos de extração falharam")

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    def _extraction_chain(self):
        """Retorna métodos disponíveis em ordem de preferência."""
        chain = []
        try:
            import pdfplumber  # noqa: F401
            chain.append(("pdfplumber", self._extract_pdfplumber))
        except ImportError:
            pass
        try:
            import fitz  # noqa: F401
            chain.append(("fitz", self._extract_fitz))
        except ImportError:
            pass
        return chain

    def _extract_pdfplumber(self, path: Path) -> Tuple[str, List[Dict], Dict[str, Any]]:
        import pdfplumber

        pages_data: List[Dict] = []
        full_text = ""

        with pdfplumber.open(path) as pdf:
            meta = {"page_count": len(pdf.pages), "method": "pdfplumber"}
            for i, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    full_text += f"\n[Página {i}]\n{page_text}\n"
                    pages_data.append({"page": i, "text": page_text})

        return full_text, pages_data, meta

    def _extract_fitz(self, path: Path) -> Tuple[str, List[Dict], Dict[str, Any]]:
        import fitz

        pages_data: List[Dict] = []
        full_text = ""

        doc = fitz.open(str(path))
        meta = {"page_count": len(doc), "method": "fitz"}

        for i, page in enumerate(doc, start=1):
            page_text = page.get_text()
            if page_text.strip():
                full_text += f"\n[Página {i}]\n{page_text}\n"
                pages_data.append({"page": i, "text": page_text})

        doc.close()
        return full_text, pages_data, meta

    @staticmethod
    def _assess_quality(text: str) -> float:
        """Score simples de qualidade baseado em heurísticas."""
        if len(text) > 2000:
            return 1.0
        if len(text) > 500:
            return 0.75
        if len(text) > 100:
            return 0.5
        return 0.25
