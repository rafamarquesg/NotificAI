"""DocumentMetadataExtractor — data, autor e serviço do documento."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from classifier import DocumentClassifier
from config import DocumentType
from extractor import PageInfo


@dataclass
class DocumentMetadata:
    document_date: Optional[str] = None
    document_type: DocumentType = DocumentType.OUTROS
    creation_date: Optional[str] = None
    author: Optional[str] = None
    service: Optional[str] = None


_DATE_RE = re.compile(r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})")
_MEDICAL_DATE_PATTERNS = [
    re.compile(r"data\s+(?:de\s+)?(?:atendimento|consulta|avaliação)[\s:]*" + _DATE_RE.pattern, re.IGNORECASE),
    re.compile(r"(?:atendimento|consulta|avaliação)\s+(?:em|de|realizad[oa]\s+em)[\s:]*" + _DATE_RE.pattern, re.IGNORECASE),
    re.compile(r"evolução\s+(?:de|em)[\s:]*" + _DATE_RE.pattern, re.IGNORECASE),
    re.compile(r"prontuário\s+(?:de|em)[\s:]*" + _DATE_RE.pattern, re.IGNORECASE),
    re.compile(r"(?:data|em)[\s:]*" + _DATE_RE.pattern, re.IGNORECASE),
    _DATE_RE,
]
_CREATION_RE = re.compile(r"(?:criado|gerado|data\s+de\s+criação)\s+(?:em)?[\s:]*" + _DATE_RE.pattern, re.IGNORECASE)
_AUTHOR_RE = re.compile(r"(?:dr\.?|dra\.?|médico|enfermeiro)[\s:]+([A-ZÁ-Úa-zá-ú]+(?:\s+[A-ZÁ-Úa-zá-ú]+){1,4})")
_SERVICE_RE = re.compile(r"(?:serviço|clínica|departamento|unidade|setor)\s+(?:de\s+)?([A-ZÁ-Ú][A-Za-zá-ú\s]{2,30})", re.IGNORECASE)


def _normalize_date(s: str) -> str:
    s = s.strip().replace("-", "/").replace(".", "/")
    parts = s.split("/")
    if len(parts) == 3:
        d, m, y = parts
        if len(y) == 2:
            yi = int(y)
            y = f"20{y}" if yi <= 30 else f"19{y}"
        return f"{int(d):02d}/{int(m):02d}/{y}"
    return s


def _is_valid_medical_date(s: str) -> bool:
    try:
        d, m, y = map(int, s.split("/"))
    except Exception:
        return False
    return 1 <= d <= 31 and 1 <= m <= 12 and 1980 <= y <= 2030


class DocumentMetadataExtractor:
    def __init__(self):
        self.classifier = DocumentClassifier()

    def extract(self, full_text: str, pages: list[PageInfo]) -> DocumentMetadata:
        header = pages[0].text if pages else full_text[:1000]
        footer = pages[-1].text if len(pages) > 1 else full_text[-1000:]
        scope = header + "\n" + footer

        date = self._find_date(scope) or self._find_date(full_text[:2000])
        creation = None
        m = _CREATION_RE.search(scope)
        if m:
            cand = _normalize_date(m.group(1))
            if _is_valid_medical_date(cand):
                creation = cand

        author_match = _AUTHOR_RE.search(scope)
        service_match = _SERVICE_RE.search(scope)

        return DocumentMetadata(
            document_date=date,
            document_type=self.classifier.classify(full_text),
            creation_date=creation,
            author=author_match.group(1).strip()[:50] if author_match else None,
            service=service_match.group(1).strip()[:30] if service_match else None,
        )

    @staticmethod
    def _find_date(text: str) -> Optional[str]:
        for pattern in _MEDICAL_DATE_PATTERNS:
            for m in pattern.finditer(text):
                cand = _normalize_date(m.group(1))
                if _is_valid_medical_date(cand):
                    return cand
        return None
