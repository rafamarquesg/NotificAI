"""
OCR para PDFs escaneados — PyMuPDF + pytesseract.

Usa PyMuPDF (já instalado) para renderizar cada página como imagem,
sem depender de poppler (pdf2image). Requer apenas:
  - pytesseract  (pip install pytesseract)
  - Tesseract OCR binário  (ver instruções abaixo)

Instalação do Tesseract no Windows:
  Baixar em: https://github.com/UB-Mannheim/tesseract/wiki
  Marcar "Portuguese" no instalador.
  Caminho padrão: C:\\Program Files\\Tesseract-OCR\\tesseract.exe
"""

import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caminhos padrão do Tesseract por plataforma
# ---------------------------------------------------------------------------
_TESSERACT_WIN_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\rafae\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]


def _find_tesseract() -> Optional[str]:
    """Localiza o executável do Tesseract no sistema."""
    import shutil

    # 1. Variável de ambiente
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path and Path(env_path).exists():
        return env_path

    # 2. PATH do sistema
    found = shutil.which("tesseract")
    if found:
        return found

    # 3. Caminhos padrão Windows
    for p in _TESSERACT_WIN_PATHS:
        if Path(p).exists():
            return p

    return None


# ---------------------------------------------------------------------------
# Verificação de disponibilidade
# ---------------------------------------------------------------------------

@dataclass
class OcrStatus:
    available: bool
    tesseract_path: Optional[str]
    version: Optional[str]
    message: str


def check_ocr() -> OcrStatus:
    """Verifica se OCR está disponível e retorna status detalhado."""
    try:
        import pytesseract
    except ImportError:
        return OcrStatus(
            available=False,
            tesseract_path=None,
            version=None,
            message=(
                "pytesseract não instalado. Execute:\n"
                "pip install pytesseract"
            ),
        )

    tess_path = _find_tesseract()
    if not tess_path:
        return OcrStatus(
            available=False,
            tesseract_path=None,
            version=None,
            message=(
                "Tesseract OCR não encontrado. Instale em:\n"
                "https://github.com/UB-Mannheim/tesseract/wiki\n"
                "Marque 'Portuguese' no instalador e reinicie o sistema."
            ),
        )

    # Configurar caminho
    pytesseract.pytesseract.tesseract_cmd = tess_path

    try:
        version = pytesseract.get_tesseract_version()
        return OcrStatus(
            available=True,
            tesseract_path=tess_path,
            version=str(version),
            message=f"Tesseract {version} disponível em: {tess_path}",
        )
    except Exception as e:
        return OcrStatus(
            available=False,
            tesseract_path=tess_path,
            version=None,
            message=f"Tesseract encontrado mas falhou ao iniciar: {e}",
        )


# Cache do status (verificado uma vez por sessão)
_ocr_status: Optional[OcrStatus] = None


def get_ocr_status() -> OcrStatus:
    global _ocr_status
    if _ocr_status is None:
        _ocr_status = check_ocr()
        if _ocr_status.available:
            logger.info("OCR disponível: %s", _ocr_status.message)
        else:
            logger.warning("OCR indisponível: %s", _ocr_status.message)
    return _ocr_status


# ---------------------------------------------------------------------------
# Extração OCR
# ---------------------------------------------------------------------------

def extract_text_ocr(
    file_bytes: bytes,
    lang: str = "por",
    dpi: int = 200,
    max_pages: Optional[int] = None,
) -> Tuple[str, int, str]:
    """
    Extrai texto de um PDF escaneado via OCR.

    Usa PyMuPDF para renderizar cada página como imagem (sem poppler),
    depois pytesseract para reconhecimento de caracteres em português.

    Args:
        file_bytes: conteúdo do PDF em bytes.
        lang:       idioma Tesseract (padrão: "por" = português).
        dpi:        resolução de renderização (padrão: 200 DPI).
        max_pages:  limitar número de páginas (None = todas).

    Returns:
        (texto_completo, num_paginas, metodo)
    """
    status = get_ocr_status()
    if not status.available:
        raise RuntimeError(f"OCR indisponível: {status.message}")

    import fitz  # PyMuPDF
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = status.tesseract_path

    doc    = fitz.open(stream=file_bytes, filetype="pdf")
    pages  = list(doc)
    if max_pages:
        pages = pages[:max_pages]

    texts: List[str] = []
    zoom   = dpi / 72  # fator de escala para o DPI desejado
    matrix = fitz.Matrix(zoom, zoom)

    for i, page in enumerate(pages):
        try:
            pix  = page.get_pixmap(matrix=matrix, alpha=False)
            img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang=lang)
            texts.append(f"--- PÁGINA {i + 1} (OCR) ---\n{text.strip()}")
            logger.debug("OCR página %d: %d chars", i + 1, len(text))
        except Exception as exc:
            logger.warning("OCR falhou na página %d: %s", i + 1, exc)
            texts.append(f"--- PÁGINA {i + 1} (OCR FALHOU) ---")

    doc.close()
    full_text = "\n\n".join(texts)
    return full_text, len(pages), "ocr_pytesseract"
