"""Sistema de pontuação e classificação de severidade.

Limiares descritos na metodologia:
  CRÍTICO   ≥ 10.0
  ALTO      6.0  – 9.9
  MODERADO  3.0  – 5.9
  BAIXO     1.0  – 2.9
  MÍNIMO    <  1.0

Ajuste automático de 30% nos limiares (para baixo) quando padrões críticos
são detectados (armas, ameaças, violência sexual, gravidez, crianças).
"""

from __future__ import annotations

from dataclasses import dataclass

SEVERITY_BANDS = (
    ("CRITICO", 10.0),
    ("ALTO", 6.0),
    ("MODERADO", 3.0),
    ("BAIXO", 1.0),
    ("MINIMO", 0.0),
)

CRITICAL_ADJUSTMENT = 0.7


@dataclass
class SeverityClassification:
    label: str
    final_score: float
    adjusted_thresholds: bool


def classify_severity(final_score: float, has_critical_pattern: bool = False) -> SeverityClassification:
    multiplier = CRITICAL_ADJUSTMENT if has_critical_pattern else 1.0
    for label, threshold in SEVERITY_BANDS:
        if final_score >= threshold * multiplier:
            return SeverityClassification(
                label=label,
                final_score=round(final_score, 3),
                adjusted_thresholds=has_critical_pattern,
            )
    return SeverityClassification(label="MINIMO", final_score=round(final_score, 3),
                                  adjusted_thresholds=has_critical_pattern)
