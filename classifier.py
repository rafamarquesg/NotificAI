"""
Classificador de tipos de notificação de violência.

Arquitetura dual:
- **Modo regras** (padrão): operacional imediatamente, sem dados rotulados.
  Usa os padrões do FeatureExtractor para inferir o tipo mais provável.
- **Modo ML**: ativado via `fit()` ou `load()` quando dados rotulados existem.
  Usa scikit-learn com as características do FeatureExtractor como entrada.

A interface é idêntica nos dois modos, permitindo substituição transparente
quando o modelo for treinado com dados reais.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline as SKPipeline
    import joblib

    HAS_SKLEARN = True
except ImportError:  # pragma: no cover
    HAS_SKLEARN = False

try:
    from .features import FeatureExtractor
    from .notification_types import NotificationType
except ImportError:
    from features import FeatureExtractor
    from notification_types import NotificationType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Motor de regras (fallback quando não há modelo treinado)
# ---------------------------------------------------------------------------

# Cada regra define: quais pattern_flags activam o tipo, quais categorias
# lexicais contribuem e o peso mínimo necessário nessas categorias.
_RULES: Dict[NotificationType, Dict] = {
    # Tipos ativados APENAS por flags de padrão (alta precisão)
    NotificationType.VIOLENCIA_SEXUAL: {
        "required_flag": "sexual_violence",
        "bonus_categories": set(),
        "min_cat_score": 0.0,
        "rule_weight": 3.0,
    },
    NotificationType.VIOLENCIA_AUTOPROVOCADA: {
        "required_flag": "self_harm",
        "bonus_categories": set(),
        "min_cat_score": 0.0,
        "rule_weight": 3.0,
    },
    NotificationType.TRAFICO_PESSOAS: {
        "required_flag": "human_trafficking",
        "bonus_categories": set(),
        "min_cat_score": 0.0,
        "rule_weight": 3.0,
    },
    NotificationType.TRABALHO_INFANTIL: {
        "required_flag": "child_labor",
        "bonus_categories": set(),
        "min_cat_score": 0.0,
        "rule_weight": 3.0,
    },
    # Tipos ativados por flag + bônus de categoria
    NotificationType.NEGLIGENCIA: {
        "required_flag": "neglect",
        "bonus_categories": {"child_specific"},
        "min_cat_score": 2.0,
        # Peso elevado para superar bônus de medical_formal em VIOLENCIA_FISICA
        # (termos de negligência frequentemente aparecem em medical_formal)
        "rule_weight": 4.0,
    },
    NotificationType.VIOLENCIA_PSICOLOGICA: {
        "required_flag": "psychological_control",
        "bonus_categories": {"psychological_abuse", "maria_penha_domestic"},
        "min_cat_score": 3.0,
        "rule_weight": 2.0,
    },
    # Tipo ativado por pontuação lexical geral (sem flag obrigatória)
    NotificationType.VIOLENCIA_FISICA: {
        "required_flag": None,
        "bonus_categories": {"medical_formal", "legal_police", "colloquial_popular"},
        "min_cat_score": 2.0,
        "rule_weight": 0.0,
    },
}


def _rule_based_scores(features: dict) -> Dict[NotificationType, float]:
    """Calcula pontuação de cada tipo com base nas regras."""
    # Inicializa todos os tipos com zero (incluindo OUTROS)
    scores: Dict[NotificationType, float] = {t: 0.0 for t in NotificationType}

    for ntype, rule in _RULES.items():
        score = 0.0
        required = rule.get("required_flag")

        # Tipo com flag obrigatória: só pontua se o padrão estiver presente
        if required is not None:
            if not features["pattern_flags"].get(required):
                continue  # flag ausente — pontuação permanece 0
            score += rule["rule_weight"]

        # Bônus de categorias lexicais
        for cat in rule.get("bonus_categories", set()):
            cat_score = features["category_scores"].get(cat, 0.0)
            if cat_score >= rule["min_cat_score"]:
                score += cat_score * 0.5

        scores[ntype] = score

    return scores


def _softmax_confidence(scores: Dict[NotificationType, float]) -> Dict[NotificationType, float]:
    """Normaliza pontuações brutas para [0, 1] com softmax."""
    values = np.array(list(scores.values()), dtype=np.float64)
    exp_v = np.exp(values - values.max())  # estabilidade numérica
    softmax_v = exp_v / exp_v.sum()
    return {ntype: float(round(p, 4)) for ntype, p in zip(scores.keys(), softmax_v)}


# ---------------------------------------------------------------------------
# Classificador principal
# ---------------------------------------------------------------------------


class NotificationClassifier:
    """
    Classifica o tipo de notificação de violência a partir do texto.

    **Sem dados rotulados** — use diretamente com regras:
        clf = NotificationClassifier()
        ntype, conf = clf.predict("Paciente vítima de estupro.")

    **Com dados rotulados** — treine e salve o modelo:
        clf = NotificationClassifier()
        clf.fit(texts, labels)   # labels: List[NotificationType]
        clf.save("modelo_nuve.pkl")
        # Ou carregue depois:
        clf = NotificationClassifier.load("modelo_nuve.pkl")
        ntype, conf = clf.predict(texto)

    O método `predict` usa automaticamente ML quando o modelo estiver treinado
    e cai de volta para regras caso contrário — sem alterar o código chamador.
    """

    def __init__(self, estimator: Optional[object] = None) -> None:
        """
        Args:
            estimator: estimador scikit-learn personalizado (opcional).
                       Padrão: LogisticRegression com StandardScaler.
        """
        self._extractor = FeatureExtractor()
        self._model: Optional[object] = None
        self._classes: Optional[List[str]] = None
        self._is_trained = False

        if estimator is not None:
            self._base_estimator = estimator
        elif HAS_SKLEARN:
            self._base_estimator = SKPipeline([
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=42,
                        solver="lbfgs",
                    ),
                ),
            ])
        else:
            self._base_estimator = None

    # ------------------------------------------------------------------
    # Treinamento
    # ------------------------------------------------------------------

    def fit(
        self,
        texts: List[str],
        labels: List[NotificationType],
    ) -> "NotificationClassifier":
        """
        Treina o classificador com amostras rotuladas.

        Args:
            texts:  Textos de prontuário (List[str]).
            labels: Tipo de notificação correspondente (List[NotificationType]).

        Returns:
            self — para encadeamento de chamadas.

        Raises:
            ImportError: scikit-learn não está instalado.
            ValueError:  tamanhos de texts e labels divergem.
        """
        if not HAS_SKLEARN:
            raise ImportError(
                "scikit-learn é necessário para treinar. "
                "Execute: pip install scikit-learn"
            )
        if len(texts) != len(labels):
            raise ValueError(
                f"texts tem {len(texts)} itens mas labels tem {len(labels)}."
            )
        if len(texts) == 0:
            raise ValueError("Nenhuma amostra fornecida para treinamento.")

        logger.info("Extraindo características de %d amostras…", len(texts))
        X = self._extractor.vectorize_batch(texts)
        y = [lbl.value for lbl in labels]

        self._classes = list(dict.fromkeys(y))  # preserva ordem de inserção
        logger.info(
            "Treinando modelo com %d amostras e %d classes…",
            len(texts),
            len(self._classes),
        )
        self._model = self._base_estimator
        self._model.fit(X, y)
        self._is_trained = True
        logger.info("Treinamento concluído.")
        return self

    # ------------------------------------------------------------------
    # Predição
    # ------------------------------------------------------------------

    def predict(self, text: str) -> Tuple[NotificationType, float]:
        """
        Prediz o tipo de notificação para um texto.

        Retorna:
            (NotificationType, confiança: float entre 0 e 1)

        Usa ML quando disponível; caso contrário, usa regras.
        """
        if self._is_trained and HAS_SKLEARN:
            return self._ml_predict(text)
        return self._rules_predict(text)

    def predict_proba(self, text: str) -> Dict[NotificationType, float]:
        """
        Retorna a distribuição de probabilidade sobre todos os tipos.

        Quando não há modelo treinado, distribui com base nas regras (softmax).
        """
        if self._is_trained and HAS_SKLEARN:
            return self._ml_predict_proba(text)
        return self._rules_predict_proba(text)

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """
        Serializa o modelo treinado em disco (formato joblib).

        Args:
            path: caminho do arquivo de saída (ex: "modelo_nuve.pkl").
        """
        if not self._is_trained:
            raise RuntimeError("Nenhum modelo treinado. Chame fit() primeiro.")
        if not HAS_SKLEARN:
            raise ImportError("joblib não disponível.")
        payload = {"model": self._model, "classes": self._classes}
        joblib.dump(payload, path)
        logger.info("Modelo salvo em: %s", path)

    @classmethod
    def load(cls, path: str) -> "NotificationClassifier":
        """
        Carrega um modelo previamente salvo por `save()`.

        Args:
            path: caminho do arquivo .pkl.

        Returns:
            NotificationClassifier com modelo ML pronto para uso.
        """
        if not HAS_SKLEARN:
            raise ImportError("joblib não disponível.")
        payload = joblib.load(path)
        instance = cls()
        instance._model = payload["model"]
        instance._classes = payload["classes"]
        instance._is_trained = True
        logger.info("Modelo carregado de: %s", path)
        return instance

    # ------------------------------------------------------------------
    # Propriedades
    # ------------------------------------------------------------------

    @property
    def is_trained(self) -> bool:
        """True se o modelo ML foi treinado ou carregado."""
        return self._is_trained

    @property
    def feature_names(self) -> List[str]:
        """Nomes das características usadas pelo modelo."""
        return self._extractor.feature_names

    # ------------------------------------------------------------------
    # Internos — ML
    # ------------------------------------------------------------------

    def _ml_predict(self, text: str) -> Tuple[NotificationType, float]:
        X = self._extractor.vectorize(text).reshape(1, -1)
        label_str = self._model.predict(X)[0]
        ntype = self._str_to_type(label_str)
        proba = self._ml_predict_proba(text)
        return ntype, proba.get(ntype, 0.0)

    def _ml_predict_proba(self, text: str) -> Dict[NotificationType, float]:
        X = self._extractor.vectorize(text).reshape(1, -1)
        proba_array = self._model.predict_proba(X)[0]
        classes = self._model.classes_
        return {
            self._str_to_type(label): round(float(p), 4)
            for label, p in zip(classes, proba_array)
        }

    # ------------------------------------------------------------------
    # Internos — regras
    # ------------------------------------------------------------------

    def _rules_predict(self, text: str) -> Tuple[NotificationType, float]:
        proba = self._rules_predict_proba(text)
        best = max(proba, key=lambda t: proba[t])
        return best, proba[best]

    def _rules_predict_proba(self, text: str) -> Dict[NotificationType, float]:
        features = self._extractor.extract(text)
        raw_scores = _rule_based_scores(features)
        # Se nenhuma regra disparou, retorna OUTROS com confiança zero
        if max(raw_scores.values()) == 0.0:
            return {t: (1.0 if t == NotificationType.OUTROS else 0.0) for t in NotificationType}
        return _softmax_confidence(raw_scores)

    # ------------------------------------------------------------------
    # Utilitário
    # ------------------------------------------------------------------

    @staticmethod
    def _str_to_type(label: str) -> NotificationType:
        try:
            return next(t for t in NotificationType if t.value == label)
        except StopIteration:
            return NotificationType.OUTROS
