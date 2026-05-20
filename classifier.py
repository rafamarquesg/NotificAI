"""DocumentClassifier — classifica o tipo de documento médico."""

from __future__ import annotations

import re

from config import DocumentType

_PATTERNS = {
    DocumentType.EVOLUCAO_MEDICA: [
        r"evolução\s+médica", r"evolução\s+clínica", r"evolução\s+do\s+paciente",
        r"prescrição\s+médica", r"exame\s+físico", r"conduta\s+médica",
        r"diagnóstico\s+médico", r"avaliação\s+médica", r"médico\s+assistente",
        r"\bdr\.?\b", r"\bdra\.?\b", r"\bcrm\b", r"clínica\s+médica",
    ],
    DocumentType.ANOTACOES_ENFERMAGEM: [
        r"anotações?\s+(?:de\s+)?enfermagem", r"evolução\s+(?:de\s+)?enfermagem",
        r"cuidados?\s+(?:de\s+)?enfermagem", r"técnico\s+(?:de\s+)?enfermagem",
        r"enfermeiro\s+responsável", r"procedimento\s+(?:de\s+)?enfermagem",
        r"sinais\s+vitais", r"balanço\s+hídrico", r"\bcoren\b",
        r"auxiliar\s+de\s+enfermagem",
    ],
    DocumentType.MULTIPROFISSIONAL: [
        r"(?:equipe\s+)?multiprofissional", r"serviço\s+social",
        r"psicologia", r"fisioterapia", r"nutrição",
        r"terapia\s+ocupacional", r"fonoaudiologia",
        r"assistente\s+social", r"psicólogo", r"fisioterapeuta",
        r"nutricionista", r"terapeuta\s+ocupacional", r"fonoaudiólogo",
    ],
}

_COMPILED = {dt: [re.compile(p, re.IGNORECASE) for p in pats]
             for dt, pats in _PATTERNS.items()}


class DocumentClassifier:
    def classify(self, text: str) -> DocumentType:
        sample = text[:2000].lower()
        scores = {dt: sum(len(rx.findall(sample)) for rx in rxs)
                  for dt, rxs in _COMPILED.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else DocumentType.OUTROS
