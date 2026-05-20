"""Composição de sensibilidade — IC95% pelo método Wilson score.

Conforme metodologia: sensibilidade = TP / (TP + FN), com IC95% pelo
método Wilson score (apropriado para proporções, especialmente quando
próximas de 0 ou 1). Reproduz exatamente o cálculo reportado no TCC:
129/152 = 84,9% (IC95% 78,4%–89,8%).
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


def composite_sensitivity(detected: int, total_positive: int,
                          contextual_high_risk: int = 0) -> dict:
    """Composição em dois níveis, alinhada à seção 'Sensibilidade expandida'.

    - sensibilidade_explicita: detecções por matching lexical direto
    - sensibilidade_expandida: explícita + score contextual de alto risco
    """
    explicit_lo, explicit_hi = wilson_score_interval(detected, total_positive)
    explicit = SensitivityResult(
        sensitivity=detected / total_positive if total_positive else 0.0,
        ci_lower=explicit_lo, ci_upper=explicit_hi,
        detected=detected, total=total_positive,
    )

    expanded_n = detected + contextual_high_risk
    exp_lo, exp_hi = wilson_score_interval(expanded_n, total_positive)
    expanded = SensitivityResult(
        sensitivity=expanded_n / total_positive if total_positive else 0.0,
        ci_lower=exp_lo, ci_upper=exp_hi,
        detected=expanded_n, total=total_positive,
    )

    return {"explicita": explicit, "expandida": expanded}


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"
