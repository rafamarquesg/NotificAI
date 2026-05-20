"""Classificação de severidade do escore final.

Limiares descritos na metodologia do TCC, com ajuste de 30% (para baixo)
quando padrões críticos são detectados.
"""

from __future__ import annotations

from dataclasses import dataclass

from analyzer import ViolencePatterns
from config import CRITICAL_THRESHOLD_MULTIPLIER, SEVERITY_THRESHOLDS, SeverityLevel


@dataclass
class SeverityClassification:
    label: str
    score: float
    adjusted_thresholds: bool


def classify_severity(total_score: float, patterns: ViolencePatterns) -> SeverityClassification:
    multiplier = CRITICAL_THRESHOLD_MULTIPLIER if patterns.any_critical() else 1.0
    for level in (SeverityLevel.CRITICAL, SeverityLevel.HIGH,
                  SeverityLevel.MODERATE, SeverityLevel.LOW, SeverityLevel.MINIMAL):
        if total_score >= SEVERITY_THRESHOLDS[level] * multiplier:
            return SeverityClassification(
                label=level.value, score=round(total_score, 3),
                adjusted_thresholds=multiplier != 1.0,
            )
    return SeverityClassification(
        label=SeverityLevel.NONE.value, score=round(total_score, 3),
        adjusted_thresholds=multiplier != 1.0,
    )
