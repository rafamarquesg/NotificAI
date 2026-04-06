"""
Extração de características (NLP) para uso em modelos de Machine Learning.

O FeatureExtractor converte um texto em:
  - Pontuações e contagens por categoria lexical  (detector.py)
  - Flags de padrões clínicos específicos         (regex curado)
  - Estatísticas básicas do texto                 (comprimento, sentenças…)
  - Embeddings BERT (opcional, via embedder.py)   — BioBERTpt / BERTimbau

Quando `embedder` é fornecido, os vetores lexicais e os embeddings BERT são
concatenados em um único vetor enriquecido. Isso permite que o classificador
downstream use tanto o conhecimento lexical curado quanto a representação
semântica densa do modelo de linguagem clínico pré-treinado.

Hierarquia de riqueza de representação:
  Lexical only (~35 dims)  <  Lexical + BERT (~803 dims)  <  BERT fine-tuned

Quando dados rotulados estiverem disponíveis, o mesmo vetor será usado para
treinar e avaliar os modelos de ML.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from .detector import ViolenceDetector
    from .embedder import BertEmbedder
except ImportError:
    from detector import ViolenceDetector
    try:
        from embedder import BertEmbedder
    except ImportError:
        BertEmbedder = None  # type: ignore


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


def _build_feature_names(
    lexicon_categories: List[str],
    bert_dim: int = 0,
) -> List[str]:
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
    # Dimensões BERT concatenadas ao final (quando embedder presente)
    for i in range(bert_dim):
        names.append(f"bert_{i}")
    return names


class FeatureExtractor:
    """
    Converte texto em vetor numérico para uso em classificadores de ML.

    Modo lexical (~35 dims):
        extractor = FeatureExtractor()

    Modo léxico + BERT (~803 dims com BioBERTpt/BERTimbau):
        from embedder import BertEmbedder
        embedder = BertEmbedder("pucpr/biobertpt-clin")
        extractor = FeatureExtractor(embedder=embedder)

    As características BERT (mean-pooled, L2-normalizadas) são concatenadas
    ao vetor lexical, permitindo que o classificador downstream use tanto
    o conhecimento curado quanto a semântica densa do LM clínico.

    Uso:
        features = extractor.extract("Paciente com violência doméstica.")
        X = extractor.vectorize("Paciente com violência doméstica.")
        X_batch = extractor.vectorize_batch(["texto1", "texto2"])
    """

    def __init__(self, embedder: Optional["BertEmbedder"] = None) -> None:
        """
        Args:
            embedder: instância de BertEmbedder (opcional).
                      Quando fornecido, os embeddings BERT são concatenados
                      ao vetor lexical. Quando None, modo lexical puro.
        """
        self._detector = ViolenceDetector()
        self._embedder = embedder
        bert_dim = embedder.embedding_dim if embedder is not None else 0
        self._feature_names: List[str] = _build_feature_names(
            list(self._detector.lexicon.keys()),
            bert_dim=bert_dim,
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @property
    def feature_names(self) -> List[str]:
        """Lista com o nome de cada dimensão do vetor de características."""
        return list(self._feature_names)

    @property
    def uses_bert(self) -> bool:
        """True se um embedder BERT está configurado."""
        return self._embedder is not None

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
              "bert_embedding":  np.ndarray ou None,
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

        bert_embedding: Optional[np.ndarray] = None
        if self._embedder is not None:
            bert_embedding = self._embedder.embed(text)

        return {
            "category_scores": category_scores,
            "category_counts": category_counts,
            "negated_count": negated_count,
            "total_score": total_score,
            "pattern_flags": _detect_patterns(text),
            "text_stats": _text_stats(text),
            "bert_embedding": bert_embedding,
        }

    def vectorize(self, text: str) -> np.ndarray:
        """Converte texto diretamente em vetor numpy para uso em sklearn."""
        return self._to_vector(self.extract(text))

    def vectorize_batch(self, texts: List[str]) -> np.ndarray:
        """
        Vetoriza uma lista de textos; retorna matriz (n_samples, n_features).

        Quando um embedder BERT está configurado, usa embed_batch() para
        processar todos os textos de uma vez (mais eficiente que chamadas
        individuais).
        """
        if self._embedder is not None:
            # Extrair partes lexicais individualmente
            lexical_vecs = np.vstack([
                self._to_vector(self.extract(t), skip_bert=True)
                for t in texts
            ])
            # Embeddings BERT em lote (mais eficiente)
            bert_vecs = self._embedder.embed_batch(texts)
            return np.hstack([lexical_vecs, bert_vecs])

        return np.vstack([self.vectorize(t) for t in texts])

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _to_vector(
        self,
        features: Dict[str, Any],
        skip_bert: bool = False,
    ) -> np.ndarray:
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
        lexical_vec = np.array(values, dtype=np.float32)

        if skip_bert or features.get("bert_embedding") is None:
            return lexical_vec

        return np.concatenate([lexical_vec, features["bert_embedding"]])
