"""
ingestion/ocr.py
================
Extrator OCR para PDFs escaneados e imagens (PNG, JPG, TIFF, BMP).
Usa pytesseract com modelo de língua portuguesa.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from .base import AbstractExtractor, ExtractionResult

_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"]
_PDF_EXTENSION = [".pdf"]


class OcrExtractor(AbstractExtractor):
    supported_extensions = _PDF_EXTENSION + _IMAGE_EXTENSIONS

    def __init__(self, dpi: int = 300, lang: str = "por"):
        self.dpi = dpi
        self.lang = lang

    def extract(self, file_path: Path) -> ExtractionResult:
        if not file_path.exists():
            return self._build_error_result(file_path, "ocr", f"Arquivo não encontrado: {file_path}")

        try:
            import pytesseract
        except ImportError:
            return self._build_error_result(file_path, "ocr", "pytesseract não instalado")

        ext = file_path.suffix.lower()

        try:
            if ext == ".pdf":
                text, pages, meta = self._ocr_from_pdf(file_path)
            elif ext in _IMAGE_EXTENSIONS:
                text, pages, meta = self._ocr_from_image(file_path)
            else:
                return self._build_error_result(file_path, "ocr", f"Extensão não suportada: {ext}")

            quality = self._estimate_ocr_quality(text)
            return ExtractionResult(
                text=self._clean_text(text),
                source_path=str(file_path),
                format="ocr",
                page_count=meta.get("page_count", len(pages)),
                extraction_method="pytesseract",
                quality_score=quality,
                pages=pages,
                metadata=meta,
                warnings=[] if quality > 0.5 else ["Qualidade OCR baixa — revisar manualmente"],
            )
        except Exception as exc:
            return self._build_error_result(file_path, "ocr", str(exc))

    # ------------------------------------------------------------------

    def _ocr_from_pdf(self, path: Path) -> Tuple[str, List[Dict], Dict[str, Any]]:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(str(path), dpi=self.dpi)
        pages_data: List[Dict] = []
        full_text = ""

        for i, img in enumerate(images, start=1):
            page_text = pytesseract.image_to_string(img, lang=self.lang)
            if page_text.strip():
                full_text += f"\n[Página {i} — OCR]\n{page_text}\n"
                pages_data.append({"page": i, "text": page_text})

        return full_text, pages_data, {"page_count": len(images), "method": "pytesseract-pdf"}

    def _ocr_from_image(self, path: Path) -> Tuple[str, List[Dict], Dict[str, Any]]:
        from PIL import Image
        import pytesseract

        img = Image.open(path)
        text = pytesseract.image_to_string(img, lang=self.lang)
        pages = [{"page": 1, "text": text}] if text.strip() else []
        return text, pages, {"page_count": 1, "method": "pytesseract-image"}

    @staticmethod
    def _estimate_ocr_quality(text: str) -> float:
        """Estima qualidade do OCR por proporção de caracteres válidos."""
        if not text:
            return 0.0
        import re
        valid = len(re.findall(r'[a-zA-ZÀ-ÿ0-9\s]', text))
        ratio = valid / max(len(text), 1)
        return round(min(ratio, 1.0), 2)
