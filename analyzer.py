"""EnhancedViolenceAnalyzer — análise lexical com contexto e padrões críticos.

Implementa as etapas 4 a 6 do pipeline descrito na metodologia:
  - Matching por regex compilado, contexto ±200 chars
  - Detecção de negação (janela de ~80 chars / 5 palavras)
  - Fator de intensidade contextual (frequência, gravidade, armas)
  - Detecção de padrões críticos (chronic, sexual, weapons, etc.)
  - Localização página/linha de cada detecção
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from config import PATTERN_BONUSES, ProcessingConfig
from extractor import ExtractionResult, PageInfo
from lexicon import (ExpandedViolenceLexicon, compile_negation_patterns,
                     compile_term_patterns)


_CONTEXT_HALF = 150
_NEG_LOOKBACK = 150
_SENTENCE_BOUNDARY = re.compile(r"[.!?\n]")
_PAGE_MARKER_RE = re.compile(r"---\s*PÁGINA\s*(\d+)\s*---")


@dataclass
class Detection:
    term: str
    category: str
    base_weight: float
    intensity: float
    adjusted_weight: float
    confidence: float
    context: str
    full_sentence: str
    position_start: int
    position_end: int
    page_number: int
    line_number: int
    document_date: Optional[str] = None


@dataclass
class ViolencePatterns:
    chronic_violence: bool = False
    escalation_pattern: bool = False
    weapons_involved: bool = False
    children_present: bool = False
    pregnancy_violence: bool = False
    sexual_violence: bool = False
    death_threats: bool = False
    multiple_injuries: bool = False
    psychological_control: bool = False
    economic_abuse: bool = False

    def any_critical(self) -> bool:
        return any((self.weapons_involved, self.death_threats,
                    self.sexual_violence, self.pregnancy_violence))

    def as_dict(self) -> dict:
        return {
            "chronic_violence": self.chronic_violence,
            "escalation_pattern": self.escalation_pattern,
            "weapons_involved": self.weapons_involved,
            "children_present": self.children_present,
            "pregnancy_violence": self.pregnancy_violence,
            "sexual_violence": self.sexual_violence,
            "death_threats": self.death_threats,
            "multiple_injuries": self.multiple_injuries,
            "psychological_control": self.psychological_control,
            "economic_abuse": self.economic_abuse,
        }


@dataclass
class AnalysisResult:
    detections: list[Detection]
    patterns: ViolencePatterns
    base_score: float
    contextual_bonus: float
    total_score: float
    category_scores: dict[str, float] = field(default_factory=dict)
    category_counts: dict[str, int] = field(default_factory=dict)


def _build_page_offsets(text: str, pages: list[PageInfo]) -> list[tuple[int, int, int]]:
    """Constrói (start_offset, end_offset, page_number) por página no texto consolidado."""
    if not pages:
        return [(0, len(text), 1)]
    offsets = []
    matches = list(_PAGE_MARKER_RE.finditer(text))
    if not matches:
        return [(0, len(text), 1)]
    for i, m in enumerate(matches):
        page_no = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        offsets.append((start, end, page_no))
    return offsets


def _page_for_position(pos: int, offsets: list[tuple[int, int, int]]) -> int:
    for start, end, page in offsets:
        if start <= pos < end:
            return page
    return offsets[0][2] if offsets else 1


def _line_for_position(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _extract_sentence(text: str, start: int, end: int, max_radius: int = 400) -> str:
    left = max(0, start - max_radius)
    right = min(len(text), end + max_radius)
    pre = text[left:start]
    post = text[end:right]
    pre_boundary = max((pre.rfind(c) for c in ".!?\n"), default=-1)
    sentence_start = left + (pre_boundary + 1 if pre_boundary >= 0 else 0)
    post_match = _SENTENCE_BOUNDARY.search(post)
    sentence_end = end + (post_match.end() if post_match else len(post))
    return text[sentence_start:sentence_end].strip()


class EnhancedViolenceAnalyzer:
    def __init__(self, config: ProcessingConfig | None = None):
        self.config = config or ProcessingConfig()
        self._terms = compile_term_patterns()
        self._negations = compile_negation_patterns()

    # -- API ----------------------------------------------------------------

    def analyze(self, extraction: ExtractionResult,
                document_date: Optional[str] = None) -> AnalysisResult:
        text = extraction.text
        offsets = _build_page_offsets(text, extraction.pages)

        detections = self._scan_terms(text, offsets, document_date)
        detections = self._dedup_overlapping(detections)
        patterns = self._detect_patterns(text)

        base_score = 0.0
        cat_score: dict[str, float] = {}
        cat_count: dict[str, int] = {}
        for d in detections:
            contrib = d.adjusted_weight * d.confidence
            base_score += contrib
            cat_score[d.category] = cat_score.get(d.category, 0.0) + contrib
            cat_count[d.category] = cat_count.get(d.category, 0) + 1

        bonus = self._pattern_bonus(patterns)
        total = base_score + bonus

        return AnalysisResult(
            detections=detections,
            patterns=patterns,
            base_score=round(base_score, 3),
            contextual_bonus=round(bonus, 3),
            total_score=round(total, 3),
            category_scores={k: round(v, 3) for k, v in cat_score.items()},
            category_counts=cat_count,
        )

    # -- Internal -----------------------------------------------------------

    def _scan_terms(self, text: str, offsets, document_date: Optional[str]) -> list[Detection]:
        detections: list[Detection] = []
        for pattern, term, category, weight in self._terms:
            for m in pattern.finditer(text):
                start, end = m.start(), m.end()
                if self._is_negated(text, start, end):
                    continue
                ctx = text[max(0, start - _CONTEXT_HALF): min(len(text), end + _CONTEXT_HALF)]
                ctx = re.sub(r"\s+", " ", ctx).strip()
                intensity = self._contextual_intensity(text, start, end)
                adjusted = weight * intensity
                confidence = self._confidence(ctx)
                detections.append(Detection(
                    term=term, category=category, base_weight=weight,
                    intensity=intensity, adjusted_weight=adjusted,
                    confidence=confidence, context=ctx,
                    full_sentence=_extract_sentence(text, start, end),
                    position_start=start, position_end=end,
                    page_number=_page_for_position(start, offsets),
                    line_number=_line_for_position(text, start),
                    document_date=document_date,
                ))
        return detections

    def _is_negated(self, text: str, start: int, end: int) -> bool:
        scope = text[max(0, start - _NEG_LOOKBACK): end]
        return any(rx.search(scope) for rx in self._negations)

    @staticmethod
    def _contextual_intensity(text: str, start: int, end: int) -> float:
        ctx = text[max(0, start - 200): min(len(text), end + 200)].lower()
        factor = 1.0
        for w in ExpandedViolenceLexicon.CRITICAL_KEYWORDS["chronic"]:
            if w in ctx:
                factor += 0.3
                break
        severity = ("hospital", "sangue", "fratura", "ambulância", "emergência",
                    "uti", "cirurgia", "sutura", "pontos", "internação")
        if any(s in ctx for s in severity):
            factor += 0.7
        if any(w in ctx for w in ExpandedViolenceLexicon.CRITICAL_KEYWORDS["weapons"]):
            factor += 0.6
        return max(0.1, min(5.0, factor))

    @staticmethod
    def _confidence(context: str) -> float:
        confidence = 1.0
        if len(context) < 30:
            confidence *= 0.8
        elif len(context) > 100:
            confidence *= 1.1
        medical = ("paciente", "diagnóstico", "exame", "relata",
                   "apresenta", "refere", "história")
        low = context.lower()
        med_count = sum(1 for m in medical if m in low)
        confidence *= (1 + med_count * 0.1)
        return max(0.1, min(2.0, confidence))

    @staticmethod
    def _dedup_overlapping(detections: list[Detection]) -> list[Detection]:
        ordered = sorted(detections, key=lambda d: d.position_start)
        kept: list[Detection] = []
        for d in ordered:
            overlap = next((k for k in kept
                            if d.position_start <= k.position_end
                            and d.position_end >= k.position_start), None)
            if overlap is None:
                kept.append(d)
            elif d.adjusted_weight > overlap.adjusted_weight:
                kept.remove(overlap)
                kept.append(d)
        return sorted(kept, key=lambda d: d.adjusted_weight * d.confidence, reverse=True)

    @staticmethod
    def _detect_patterns(text: str) -> ViolencePatterns:
        low = text.lower()
        kw = ExpandedViolenceLexicon.CRITICAL_KEYWORDS
        p = ViolencePatterns()
        p.chronic_violence = any(w in low for w in kw["chronic"])
        p.escalation_pattern = any(w in low for w in kw["escalation"])
        p.weapons_involved = any(w in low for w in kw["weapons"])
        p.children_present = any(w in low for w in kw["children_present"])
        p.pregnancy_violence = any(w in low for w in kw["pregnancy"])
        p.sexual_violence = any(w in low for w in kw["sexual"])
        p.death_threats = any(w in low for w in kw["death_threats"])
        p.psychological_control = any(w in low for w in kw["psychological_control"])
        p.economic_abuse = any(w in low for w in kw["economic_abuse"])
        injury_count = sum(low.count(t) for t in ExpandedViolenceLexicon.INJURY_TERMS)
        p.multiple_injuries = injury_count > 3
        return p

    @staticmethod
    def _pattern_bonus(p: ViolencePatterns) -> float:
        bonus = 0.0
        for key, value in p.as_dict().items():
            if value and key in PATTERN_BONUSES:
                bonus += PATTERN_BONUSES[key]
        return bonus
