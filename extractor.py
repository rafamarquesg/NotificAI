"""EnhancedTextExtractor — extração multi-método com informações por página.

Cascata descrita na metodologia (Fase 2, etapa 1):
  1. PDFPlumber  — primário, PDFs nativos
  2. PyMuPDF     — fallback para PDFs complexos
  3. Tesseract   — OCR para PDFs escaneados

Cada método produz `PageInfo` por página para que o analisador possa
reportar página/linha de cada detecção.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import (OCRProcessingError, PDFProcessingError, ProcessingConfig,
                    QualityLevel)


@dataclass
class PageInfo:
    page_number: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    text: str
    method: str
    pages: list[PageInfo]
    page_count: int
    char_count: int
    word_count: int
    quality: QualityLevel


PAGE_MARKER = "\n--- PÁGINA {n} ---\n"


def _quality(text: str) -> QualityLevel:
    if not text:
        return QualityLevel.POOR
    medical = ("paciente", "diagnóstico", "tratamento", "exame", "história",
               "sintomas", "medicação", "consulta", "avaliação")
    low = text.lower()
    medical_count = sum(t in low for t in medical)
    score = 0
    if len(text) > 2000:
        score += 2
    elif len(text) > 1000:
        score += 1
    if medical_count >= 3:
        score += 2
    elif medical_count >= 1:
        score += 1
    if score >= 4: return QualityLevel.EXCELLENT
    if score == 3: return QualityLevel.GOOD
    if score == 2: return QualityLevel.FAIR
    return QualityLevel.POOR


def _try_pdfplumber(path: Path) -> ExtractionResult | None:
    try:
        import pdfplumber
    except ImportError:
        return None
    try:
        pages: list[PageInfo] = []
        buf: list[str] = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                ptext = page.extract_text() or ""
                if len(ptext.strip()) < 10:
                    continue
                buf.append(PAGE_MARKER.format(n=i) + ptext)
                pages.append(PageInfo(i, ptext, {"width": page.width, "height": page.height}))
        if not pages:
            return None
        text = "".join(buf)
        return ExtractionResult(text, "pdfplumber", pages, len(pages),
                                len(text), len(text.split()), _quality(text))
    except Exception:
        return None


def _try_pymupdf(path: Path) -> ExtractionResult | None:
    try:
        import fitz
    except ImportError:
        return None
    try:
        pages: list[PageInfo] = []
        buf: list[str] = []
        doc = fitz.open(path)
        try:
            for i, page in enumerate(doc, start=1):
                ptext = page.get_text("text") or ""
                if len(ptext.strip()) < 10:
                    continue
                buf.append(PAGE_MARKER.format(n=i) + ptext)
                pages.append(PageInfo(i, ptext, {"rotation": page.rotation}))
        finally:
            doc.close()
        if not pages:
            return None
        text = "".join(buf)
        return ExtractionResult(text, "pymupdf", pages, len(pages),
                                len(text), len(text.split()), _quality(text))
    except Exception:
        return None


def _try_ocr(path: Path, config: ProcessingConfig) -> ExtractionResult | None:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return None
    try:
        images = convert_from_path(path, dpi=config.ocr_dpi,
                                   first_page=1, last_page=config.ocr_max_pages)
    except Exception as exc:
        raise OCRProcessingError(f"Conversão PDF→imagem falhou: {exc}") from exc
    pages: list[PageInfo] = []
    buf: list[str] = []
    for i, img in enumerate(images, start=1):
        try:
            ptext = pytesseract.image_to_string(img, lang="por")
        except Exception:
            continue
        if len(ptext.strip()) < 20:
            continue
        buf.append(PAGE_MARKER.format(n=i) + f"[OCR]\n{ptext}")
        pages.append(PageInfo(i, ptext, {"ocr": "pytesseract", "size": img.size}))
    if not pages:
        return None
    text = "".join(buf)
    return ExtractionResult(text, "ocr_tesseract", pages, len(pages),
                            len(text), len(text.split()), _quality(text))


class EnhancedTextExtractor:
    def __init__(self, config: ProcessingConfig | None = None):
        self.config = config or ProcessingConfig()

    def extract(self, pdf_path: str | Path) -> ExtractionResult:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.suffix.lower() != ".pdf":
            raise PDFProcessingError(f"Não é PDF: {path.suffix}")
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            raise PDFProcessingError(f"Arquivo {size_mb:.1f}MB > limite {self.config.max_file_size_mb}MB")

        for fn in (_try_pdfplumber, _try_pymupdf,
                   lambda p: _try_ocr(p, self.config)):
            result = fn(path)
            if result and len(result.text.strip()) >= self.config.min_text_quality_chars:
                return result
        raise PDFProcessingError(f"Todos os métodos de extração falharam para {path.name}")
