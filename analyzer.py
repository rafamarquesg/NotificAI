"""EnhancedViolenceAnalyzer — análise lexical com detecção de negação e contexto.

Implementação fiel à descrição na metodologia:
  - Matching por expressões regulares compiladas
  - Janela de contexto de 200 caracteres adjacentes
  - Detecção de negação em janela de 5 palavras anteriores
  - Score base: Σ(termo × peso_categoria × fator_intensidade × (1 - fator_negação))
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lexicon import (
    CRITICAL_PATTERNS,
    EVASION_MARKERS,
    ExpandedViolenceLexicon,
    NEGATION_TRIGGERS,
)

CONTEXT_WINDOW = 200
NEGATION_WINDOW_WORDS = 5
INTENSITY_MARKERS = {
    "grave": 1.3, "severo": 1.3, "extrema": 1.4, "múltiplas": 1.2,
    "repetida": 1.25, "crônica": 1.3, "recorrente": 1.25, "intensa": 1.2,
}


@dataclass
class Detection:
    term: str
    category: str
    weight: float
    position: int
    context: str
    negated: bool
    intensity_factor: float
    contribution: float


@dataclass
class ContextualSignals:
    medical_trauma_density: float = 0.0
    evasion_count: int = 0
    critical_pattern_hits: dict = field(default_factory=dict)
    paragraphs: int = 0


@dataclass
class AnalysisResult:
    detections: list[Detection]
    contextual: ContextualSignals
    base_score: float
    contextual_bonus: float
    final_score: float


def _compile_lexicon():
    compiled = []
    for term, category, weight in ExpandedViolenceLexicon.flat_terms():
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        compiled.append((pattern, term, category, weight))
    return compiled


def _is_negated(text: str, pos: int) -> bool:
    prefix = text[max(0, pos - 80):pos].lower()
    tokens = prefix.split()[-NEGATION_WINDOW_WORDS:]
    window = " ".join(tokens)
    return any(trigger in window for trigger in NEGATION_TRIGGERS)


def _intensity_factor(context: str) -> float:
    lower = context.lower()
    factor = 1.0
    for marker, mult in INTENSITY_MARKERS.items():
        if marker in lower:
            factor = max(factor, mult)
    return factor


def _context_slice(text: str, start: int, end: int) -> str:
    a = max(0, start - CONTEXT_WINDOW)
    b = min(len(text), end + CONTEXT_WINDOW)
    return text[a:b].replace("\n", " ").strip()


def _contextual_signals(text: str) -> ContextualSignals:
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    trauma_terms = ("fratura", "hematoma", "equimose", "lesão", "lesao", "trauma",
                    "ferimento", "contusão", "contusao", "escoriação", "escoriacao")
    densities = []
    for p in paragraphs:
        lower = p.lower()
        n = sum(lower.count(t) for t in trauma_terms)
        densities.append(n)
    max_density = max(densities, default=0)

    lower = text.lower()
    evasion_count = sum(lower.count(m) for m in EVASION_MARKERS)

    crit_hits = {}
    for name, (_bonus, markers) in CRITICAL_PATTERNS.items():
        n = sum(lower.count(m) for m in markers)
        if n:
            crit_hits[name] = n

    return ContextualSignals(
        medical_trauma_density=float(max_density),
        evasion_count=evasion_count,
        critical_pattern_hits=crit_hits,
        paragraphs=len(paragraphs),
    )


class EnhancedViolenceAnalyzer:
    def __init__(self):
        self._compiled = _compile_lexicon()

    def analyze(self, text: str) -> AnalysisResult:
        detections: list[Detection] = []
        seen_positions = set()

        for pattern, term, category, weight in self._compiled:
            for m in pattern.finditer(text):
                pos = m.start()
                key = (term.lower(), pos)
                if key in seen_positions:
                    continue
                seen_positions.add(key)
                ctx = _context_slice(text, pos, m.end())
                negated = _is_negated(text, pos)
                intensity = _intensity_factor(ctx)
                contribution = 0.0 if negated else weight * intensity
                detections.append(Detection(
                    term=term, category=category, weight=weight, position=pos,
                    context=ctx, negated=negated, intensity_factor=intensity,
                    contribution=round(contribution, 3),
                ))

        base_score = round(sum(d.contribution for d in detections), 3)
        contextual = _contextual_signals(text)
        contextual_bonus = self._compute_context_bonus(contextual, base_score)
        return AnalysisResult(
            detections=detections,
            contextual=contextual,
            base_score=base_score,
            contextual_bonus=round(contextual_bonus, 3),
            final_score=round(base_score + contextual_bonus, 3),
        )

    @staticmethod
    def _compute_context_bonus(signals: ContextualSignals, base_score: float) -> float:
        bonus = 0.0
        for pattern_name, count in signals.critical_pattern_hits.items():
            inc, _ = CRITICAL_PATTERNS[pattern_name]
            bonus += inc * min(count, 2)
        if base_score < 3.0 and signals.medical_trauma_density > 3:
            bonus += min(5.0, signals.medical_trauma_density - 3.0)
        if signals.evasion_count > 0:
            bonus += min(2.0, signals.evasion_count * 0.5)
        return bonus
