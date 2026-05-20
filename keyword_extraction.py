"""Extração de palavras-chave — reproduz a Tabela 2 do TCC.

Agrega frequência absoluta e relativa dos termos detectados em uma coorte,
agrupando por categoria semântica do léxico hierárquico.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from analyzer import AnalysisResult


@dataclass
class KeywordFrequency:
    term: str
    absolute: int
    relative: float
    category: str


def aggregate_keywords(results: list[AnalysisResult], top_k: int = 20) -> list[KeywordFrequency]:
    counter: Counter = Counter()
    category_index: dict[str, str] = {}
    for r in results:
        unique_terms_in_case = set()
        for d in r.detections:
            if d.negated:
                continue
            key = d.term.lower()
            unique_terms_in_case.add(key)
            category_index[key] = d.category
        for k in unique_terms_in_case:
            counter[k] += 1

    total = sum(counter.values()) or 1
    most_common = counter.most_common(top_k)
    return [
        KeywordFrequency(
            term=term,
            absolute=n,
            relative=round(100 * n / total, 2),
            category=category_index.get(term, "indefinida"),
        )
        for term, n in most_common
    ]


def to_csv_rows(frequencies: list[KeywordFrequency]) -> list[dict]:
    return [
        {"termo": f.term, "frequencia_absoluta": f.absolute,
         "frequencia_relativa_pct": f.relative, "categoria": f.category}
        for f in frequencies
    ]
