"""Extração agregada de palavras-chave — reproduz a Tabela 2 do TCC.

Conta presença única do termo por caso (não totaliza ocorrências dentro
do mesmo prontuário) e ordena por frequência absoluta.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from analyzer import AnalysisResult


@dataclass
class KeywordFrequency:
    term: str
    absolute: int
    relative_pct: float
    category: str


def aggregate_keywords(results: list[AnalysisResult],
                       top_k: int = 20) -> list[KeywordFrequency]:
    counter: Counter[str] = Counter()
    category_index: dict[str, str] = {}
    for r in results:
        seen_in_case: set[str] = set()
        for d in r.detections:
            key = d.term.lower()
            seen_in_case.add(key)
            category_index[key] = d.category
        for k in seen_in_case:
            counter[k] += 1
    total = sum(counter.values()) or 1
    most = counter.most_common(top_k)
    return [
        KeywordFrequency(term=t, absolute=n,
                         relative_pct=round(100 * n / total, 2),
                         category=category_index.get(t, "indefinida"))
        for t, n in most
    ]


def to_csv_rows(freqs: list[KeywordFrequency]) -> list[dict]:
    return [{"termo": f.term, "frequencia_absoluta": f.absolute,
             "frequencia_relativa_pct": f.relative_pct,
             "categoria": f.category} for f in freqs]
