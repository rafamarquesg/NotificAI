"""Composição de sensibilidade — IC95% pelo método Wilson score.

Conforme a metodologia do TCC, a sensibilidade é calculada apenas sobre
casos positivos confirmados (TP/(TP+FN)) e reportada com IC95% pelo
método Wilson score — apropriado para proporções próximas dos extremos.

Reproduz o resultado publicado: 129/152 = 84,9% (IC95% 78,4–89,8%).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Z_95 = 1.959963984540054


@dataclass
class SensitivityResult:
    sensitivity: float
    ci_lower: float
    ci_upper: float
    detected: int
    total: int


def wilson_score_interval(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def composite_sensitivity(detected_explicit: int, total_positive: int,
                          contextual_high_risk: int = 0) -> dict[str, SensitivityResult]:
    """Composição em dois níveis (seção 'Sensibilidade expandida' do TCC).

    - explicita: detecções por matching lexical direto (84,9% no estudo)
    - expandida: explícita + score contextual de alto risco (100% no estudo)
    """
    lo, hi = wilson_score_interval(detected_explicit, total_positive)
    explicit = SensitivityResult(
        sensitivity=(detected_explicit / total_positive) if total_positive else 0.0,
        ci_lower=lo, ci_upper=hi,
        detected=detected_explicit, total=total_positive,
    )
    expanded_n = detected_explicit + contextual_high_risk
    lo2, hi2 = wilson_score_interval(expanded_n, total_positive)
    expanded = SensitivityResult(
        sensitivity=(expanded_n / total_positive) if total_positive else 0.0,
        ci_lower=lo2, ci_upper=hi2,
        detected=expanded_n, total=total_positive,
    )
    return {"explicita": explicit, "expandida": expanded}


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"
