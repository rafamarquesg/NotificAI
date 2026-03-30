"""
nlp/negation.py
===============
Handler de negação contextual — inspirado no algoritmo NegEx (Chapman 2001)
e no ConText (Harkema 2009), adaptado para português clínico.

Objetivo: eliminar falsos positivos onde o termo de agravo aparece negado.

Exemplos de falsos positivos comuns:
  - "nega violência doméstica"
  - "sem sinais de maus-tratos"
  - "descarta abuso sexual"
  - "não há histórico de agressão"

A janela de verificação é de 80 chars ANTES do match (negação pré-nominal)
e 40 chars DEPOIS (negação pós-nominal — ex: "lesão corporal — descartada").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class NegationResult:
    is_negated: bool
    trigger: str          # Palavra que causou a negação (ex: "nega", "sem")
    window_text: str      # Trecho analisado (para auditoria)


# ---------------------------------------------------------------------------
# Termos disparadores de negação em prontuários PT-BR
# ---------------------------------------------------------------------------

_PRE_NEGATION_TRIGGERS = [
    # Verbos de negação clínica
    r'\bnega\b', r'\bnegou\b', r'\bnega(?:ndo|r)?\b',
    r'\bdescart(?:a|ou|ar|ando)\b',
    r'\bexclu(?:i|iu|ir|indo)\b',
    r'\bafasta\b', r'\bafastou\b',
    r'\bausenf(?:a|e)?\b',
    # Advérbios / preposições
    r'\bnão\b', r'\bnao\b', r'\bjamais\b', r'\bnunca\b',
    r'\bsem\b', r'\bausente\b', r'\binexist(?:ente|ência)\b',
    r'\bimprováv(?:el|eis)\b', r'\bimpossív(?:el|eis)\b',
    # Locuções clínicas
    r'\bsem\s+(?:evidências?|indícios?|sinais?|hist[oó]rico)\s+de\b',
    r'\bnão\s+(?:há|apresenta|refere|relata|constat(?:a|ou))\b',
    r'\bdescartad(?:o|a)\b',
    r'\bnão\s+identificad(?:o|a)\b',
    r'\bnão\s+sugestiv(?:o|a)\b',
]

_POST_NEGATION_TRIGGERS = [
    r'\bdescartad(?:o|a)\b',
    r'\bafastad(?:o|a)\b',
    r'\bexcluíd(?:o|a)\b',
    r'\bnão\s+confirmad(?:o|a)\b',
    r'\bnão\s+comprovad(?:o|a)\b',
]

_PRE_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PRE_NEGATION_TRIGGERS]
_POST_COMPILED = [re.compile(p, re.IGNORECASE) for p in _POST_NEGATION_TRIGGERS]

# Contextos que ANULAM a negação (double-negation / ressalva clínica)
_DOUBLE_NEG_PATTERNS = [
    re.compile(r'não\s+(?:é\s+)?possível\s+(?:descartar|excluir)', re.IGNORECASE),
    re.compile(r'não\s+se\s+pode\s+(?:afastar|excluir)', re.IGNORECASE),
    re.compile(r'suspeita(?:-se)?\s+de', re.IGNORECASE),
]


class NegationHandler:
    """
    Verifica se uma detecção ocorre num contexto de negação.

    Uso:
        handler = NegationHandler()
        result = handler.check(text, match_start=120, match_end=145)
        if result.is_negated:
            skip_detection()
    """

    def __init__(self, pre_window: int = 80, post_window: int = 40):
        self.pre_window = pre_window
        self.post_window = post_window

    def check(self, text: str, match_start: int, match_end: int) -> NegationResult:
        """
        Analisa a janela ao redor do match e decide se está negado.
        Retorna NegationResult com a decisão e o termo disparador.
        """
        pre_start = max(0, match_start - self.pre_window)
        post_end = min(len(text), match_end + self.post_window)

        pre_context = text[pre_start:match_start]
        post_context = text[match_end:post_end]
        window = pre_context + text[match_start:match_end] + post_context

        # Verifica double-negation antes (ex: "não é possível descartar")
        for dn_pattern in _DOUBLE_NEG_PATTERNS:
            if dn_pattern.search(pre_context):
                return NegationResult(is_negated=False, trigger="", window_text=window)

        # Pré-negação
        for pattern in _PRE_COMPILED:
            m = pattern.search(pre_context)
            if m:
                return NegationResult(is_negated=True, trigger=m.group(), window_text=window)

        # Pós-negação
        for pattern in _POST_COMPILED:
            m = pattern.search(post_context)
            if m:
                return NegationResult(is_negated=True, trigger=m.group(), window_text=window)

        return NegationResult(is_negated=False, trigger="", window_text=window)

    def filter_detections(self, text: str, detections: List) -> List:
        """
        Filtra lista de detecções removendo as negadas.
        Aceita qualquer objeto com `position_start` e `position_end`.
        """
        return [
            d for d in detections
            if not self.check(text, d.position_start, d.position_end).is_negated
        ]
