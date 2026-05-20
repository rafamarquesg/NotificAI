"""DocumentClassifier — identifica tipo de documento e extrai metadados."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DOC_PATTERNS = {
    "evolucao_medica": (r"evolução médica|evolucao medica|evolução clínica", 1.0),
    "anotacoes_enfermagem": (r"anotações de enfermagem|anotacoes de enfermagem|evolução de enfermagem", 1.0),
    "servico_social": (r"serviço social|servico social|relatório social", 1.0),
    "relatorio_multiprofissional": (r"relatório multiprofissional|multiprofissional", 0.9),
    "laudo": (r"laudo|exame complementar", 0.7),
    "encaminhamento": (r"encaminhamento|referência", 0.6),
}

DATE_RE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b")
AUTHOR_RE = re.compile(r"(?:dr\.?|dra\.?|enf\.?|assist\.?\s*social)\s+([A-ZÁ-Úa-zá-ú\s]+)", re.IGNORECASE)
SERVICE_RE = re.compile(r"(?:serviço|servico|unidade|setor)\s*[:\-]?\s*([A-ZÁ-Ú][A-Za-zá-ú\s]+)", re.IGNORECASE)


@dataclass
class DocumentMeta:
    doc_type: str
    confidence: float
    dates: list[str] = field(default_factory=list)
    author: str | None = None
    service: str | None = None


class DocumentClassifier:
    def classify(self, text: str) -> DocumentMeta:
        lower = text.lower()
        best_type, best_conf = "indefinido", 0.0
        for name, (pattern, weight) in DOC_PATTERNS.items():
            hits = len(re.findall(pattern, lower))
            if hits == 0:
                continue
            conf = min(1.0, hits * weight * 0.4)
            if conf > best_conf:
                best_type, best_conf = name, conf

        dates = [f"{d}/{m}/{y}" for d, m, y in DATE_RE.findall(text)]
        author_match = AUTHOR_RE.search(text)
        service_match = SERVICE_RE.search(text)
        return DocumentMeta(
            doc_type=best_type,
            confidence=round(best_conf, 3),
            dates=dates[:10],
            author=author_match.group(1).strip() if author_match else None,
            service=service_match.group(1).strip() if service_match else None,
        )
