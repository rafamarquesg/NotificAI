"""EnhancedTextExtractor — extração multi-método em cascata.

Estratégia descrita na metodologia:
  1. PDFPlumber  — método primário, PDFs nativos
  2. PyMuPDF     — fallback para documentos complexos
  3. Tesseract   — OCR para PDFs escaneados
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractionResult:
    text: str
    method: str
    pages: int
    quality_score: float


def _quality(text: str) -> float:
    if not text:
        return 0.0
    alpha = sum(1 for c in text if c.isalpha())
    total = len(text)
    if total < 50:
        return 0.0
    alpha_ratio = alpha / total
    words = [w for w in text.split() if w.isalpha()]
    if not words:
        return 0.0
    avg_len = sum(len(w) for w in words) / len(words)
    len_score = min(avg_len / 5.0, 1.0)
    return round(0.7 * alpha_ratio + 0.3 * len_score, 3)


def _extract_pdfplumber(path: Path) -> ExtractionResult | None:
    try:
        import pdfplumber
    except ImportError:
        return None
    try:
        with pdfplumber.open(path) as pdf:
            pages = pdf.pages
            text = "\n".join((p.extract_text() or "") for p in pages)
        q = _quality(text)
        if q < 0.4:
            return None
        return ExtractionResult(text=text, method="pdfplumber", pages=len(pages), quality_score=q)
    except Exception:
        return None


def _extract_pymupdf(path: Path) -> ExtractionResult | None:
    try:
        import fitz
    except ImportError:
        return None
    try:
        doc = fitz.open(path)
        text = "\n".join(page.get_text("text") for page in doc)
        n = doc.page_count
        doc.close()
        q = _quality(text)
        if q < 0.4:
            return None
        return ExtractionResult(text=text, method="pymupdf", pages=n, quality_score=q)
    except Exception:
        return None


def _extract_ocr(path: Path) -> ExtractionResult | None:
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        return None
    try:
        doc = fitz.open(path)
        chunks = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            chunks.append(pytesseract.image_to_string(img, lang="por"))
        n = doc.page_count
        doc.close()
        text = "\n".join(chunks)
        return ExtractionResult(text=text, method="ocr_tesseract", pages=n, quality_score=_quality(text))
    except Exception:
        return None


class EnhancedTextExtractor:
    def extract(self, pdf_path: str | Path) -> ExtractionResult:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(path)
        for fn in (_extract_pdfplumber, _extract_pymupdf, _extract_ocr):
            result = fn(path)
            if result and result.text.strip():
                return result
        return ExtractionResult(text="", method="failed", pages=0, quality_score=0.0)
