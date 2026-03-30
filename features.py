"""
Extração de características (NLP) para uso em modelos de Machine Learning.

O FeatureExtractor converte um texto em:
  - Pontuações e contagens por categoria lexical  (detector.py)
  - Flags de padrões clínicos específicos         (regex curado)
  - Estatísticas básicas do texto                 (comprimento, sentenças…)

Essas características formam o vetor numérico que alimentará o classificador.
Quando dados rotulados estiverem disponíveis, o mesmo vetor será usado para
treinar e avaliar os modelos de ML.
"""

import re
from typing import Any, Dict, List, Tuple

import numpy as np

try:
    from .detector import ViolenceDetector
except ImportError:
    from detector import ViolenceDetector


# ---------------------------------------------------------------------------
# Padrões clínicos de alta relevância para distinção entre tipos de notificação
# ---------------------------------------------------------------------------

_PATTERN_DEFINITIONS: Dict[str, List[str]] = {
    # Violência sexual
    "sexual_violence": [
        r"\b(estupro|abuso\s+sexual|violência\s+sexual|sexo\s+forçado|estupro\s+conjugal)\b",
        r"\b(forçou|obrigou)\b.{0,40}\b(relação|ato\s+sexual|sexo)\b",
    ],
    # Violência autoprovocada
    "self_harm": [
        r"\b(ideação\s+suicida|tentativa\s+de\s+suicídio|automutilação"
        r"|autolesão|autoextermínio|comportamento\s+autodestrutivo)\b",
    ],
    # Negligência / abandono
    "neglect": [
        r"\b(negligência|abandono\s+de\s+incapaz|desnutrição|desidratação\s+severa"
        r"|má\s+higiene|privação\s+de\s+alimentos|falta\s+de\s+higiene)\b",
    ],
    # Controle psicológico coercitivo
    "psychological_control": [
        r"\b(controle\s+coercitivo|cárcere\s+privado|isolamento\s+social\s+forçado"
        r"|proibição\s+de\s+(sair|trabalhar|estudar)|gaslighting|tortura\s+psicológica)\b",
    ],
    # Violência crônica / padrão repetido
    "chronic_violence": [
        r"\b(sempre|todo\s+dia|constantemente|frequentemente|anos|rotina|recorrente"
        r"|repetid[ao]|crônic[ao])\b.{0,60}\b(agred|bat|violent|maltrat|espanc)\w*",
    ],
    # Armas envolvidas
    "weapons_involved": [
        r"\b(arma\s+de\s+fogo|arma\s+branca|faca|revólver|pistola|martelo"
        r"|objeto\s+contundente)\b",
    ],
    # Crianças presentes durante a agressão
    "children_present": [
        r"\b(na\s+frente\s+d[ao]s?\s+crianças?|filh[oa]s?\s+(viu|assistiu|presenci)"
        r"|menor\s+exposto|crianças\s+presentes)\b",
    ],
    # Violência na gestação
    "pregnancy_violence": [
        r"\b(grávida|gestante|gestação).{0,80}(agred|bat|chut|violent|espanc)\w*",
        r"\b(agred|bat|chut|violent|espanc)\w*.{0,80}\b(grávida|gestante|barriga)\b",
    ],
    # Ameaças de morte
    "death_threats": [
        r"\b(vou\s+te\s+matar|vai\s+morrer|ameaçou\s+de\s+morte|prometeu\s+matar"
        r"|disse\s+que\s+mata)\b",
    ],
    # Lesões múltiplas (indicativo de violência grave)
    "multiple_injuries": [
        r"\b(fraturas?\s+múltiplas?|equimoses?\s+múltiplas?|hematomas?\s+múltiplos?"
        r"|politraumatismo|lesões\s+em\s+diferentes\s+estágios)\b",
    ],
    # Trabalho infantil
    "child_labor": [
        r"\b(trabalho\s+infantil|menor\s+trabalhando|criança\s+trabalha"
        r"|exploração\s+de\s+menor)\b",
    ],
    # Tráfico de pessoas
    "human_trafficking": [
        r"\b(tráfico\s+de\s+pessoas?|exploração\s+sexual\s+comercial"
        r"|escravidão\s+sexual|aliciamento)\b",
    ],
}

# Compilar uma vez em nível de módulo
_COMPILED: Dict[str, List[re.Pattern]] = {
    name: [re.compile(p, re.IGNORECASE | re.DOTALL) for p in patterns]
    for name, patterns in _PATTERN_DEFINITIONS.items()
}


def _detect_patterns(text: str) -> Dict[str, bool]:
    """Verifica quais padrões estão presentes no texto."""
    return {
        name: any(pat.search(text) for pat in patterns)
        for name, patterns in _COMPILED.items()
    }


def _text_stats(text: str) -> Dict[str, float]:
    """Estatísticas básicas do texto."""
    words = text.split()
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]
    return {
        "char_count": float(len(text)),
        "word_count": float(len(words)),
        "sentence_count": float(len(sentences)),
        "avg_word_len": (
            float(sum(len(w) for w in words) / len(words)) if words else 0.0
        ),
        "avg_sentence_len": (
            float(len(words) / len(sentences)) if sentences else 0.0
        ),
    }


def _build_feature_names(lexicon_categories: List[str]) -> List[str]:
    names: List[str] = []
    for cat in lexicon_categories:
        names.append(f"score_{cat}")
    for cat in lexicon_categories:
        names.append(f"count_{cat}")
    names.append("count_negated")
    names.append("total_score")
    for pattern_name in _PATTERN_DEFINITIONS:
        names.append(f"pattern_{pattern_name}")
    names += [
        "text_char_count",
        "text_word_count",
        "text_sentence_count",
        "text_avg_word_len",
        "text_avg_sentence_len",
    ]
    return names


class FeatureExtractor:
    """
    Converte texto em vetor numérico para uso em classificadores de ML.

    Características geradas (total ~35):
    - Pontuação acumulada por categoria lexical  (8 floats)
    - Contagem de termos por categoria           (8 ints)
    - Contagem de achados negados                (1 int)
    - Pontuação total (sem negados)              (1 float)
    - Flags de padrões clínicos                  (12 bools → 0/1)
    - Estatísticas do texto                      (5 floats)

    Uso:
        extractor = FeatureExtractor()

        # Dicionário interpretável (para debugging / logging)
        features = extractor.extract("Paciente com violência doméstica.")

        # Vetor numpy para ML
        X = extractor.vectorize("Paciente com violência doméstica.")
    """

    def __init__(self) -> None:
        self._detector = ViolenceDetector()
        self._feature_names: List[str] = _build_feature_names(
            list(self._detector.lexicon.keys())
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @property
    def feature_names(self) -> List[str]:
        """Lista com o nome de cada dimensão do vetor de características."""
        return list(self._feature_names)

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extrai características interpretáveis do texto.

        Retorno:
            {
              "category_scores": {categoria: pontuação, ...},
              "category_counts": {categoria: contagem, ...},
              "negated_count":   int,
              "total_score":     float,
              "pattern_flags":   {padrão: bool, ...},
              "text_stats":      {métrica: float, ...},
            }
        """
        detections = self._detector.analyze(text)

        category_scores: Dict[str, float] = {
            cat: 0.0 for cat in self._detector.lexicon
        }
        category_counts: Dict[str, int] = {
            cat: 0 for cat in self._detector.lexicon
        }
        negated_count = 0

        for det in detections:
            if det["negated"]:
                negated_count += 1
            else:
                category_scores[det["category"]] += det["weight"]
                category_counts[det["category"]] += 1

        total_score = sum(category_scores.values())

        return {
            "category_scores": category_scores,
            "category_counts": category_counts,
            "negated_count": negated_count,
            "total_score": total_score,
            "pattern_flags": _detect_patterns(text),
            "text_stats": _text_stats(text),
        }

    def vectorize(self, text: str) -> np.ndarray:
        """Converte texto diretamente em vetor numpy para uso em sklearn."""
        return self._to_vector(self.extract(text))

    def vectorize_batch(self, texts: List[str]) -> np.ndarray:
        """Vetoriza uma lista de textos; retorna matriz (n_samples, n_features)."""
        return np.vstack([self.vectorize(t) for t in texts])

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _to_vector(self, features: Dict[str, Any]) -> np.ndarray:
        values: List[float] = []
        for cat in self._detector.lexicon:
            values.append(features["category_scores"].get(cat, 0.0))
        for cat in self._detector.lexicon:
            values.append(float(features["category_counts"].get(cat, 0)))
        values.append(float(features["negated_count"]))
        values.append(float(features["total_score"]))
        for name in _PATTERN_DEFINITIONS:
            values.append(float(features["pattern_flags"].get(name, False)))
        stats = features["text_stats"]
        values += [
            stats["char_count"],
            stats["word_count"],
            stats["sentence_count"],
            stats["avg_word_len"],
            stats["avg_sentence_len"],
        ]
        return np.array(values, dtype=np.float32)
