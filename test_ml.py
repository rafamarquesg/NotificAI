"""
Testes para FeatureExtractor, NotificationClassifier e AnalysisPipeline.
"""

import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from features import FeatureExtractor
from notification_types import NotificationType
from classifier import NotificationClassifier
from pipeline import AnalysisPipeline

try:
    import sklearn
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def extractor():
    return FeatureExtractor()


@pytest.fixture(scope="module")
def clf():
    return NotificationClassifier()


@pytest.fixture(scope="module")
def pipeline():
    return AnalysisPipeline()


# ---------------------------------------------------------------------------
# FeatureExtractor — estrutura do output
# ---------------------------------------------------------------------------

def test_extract_returns_expected_keys(extractor):
    features = extractor.extract("Paciente com violência doméstica.")
    assert "category_scores" in features
    assert "category_counts" in features
    assert "negated_count" in features
    assert "total_score" in features
    assert "pattern_flags" in features
    assert "text_stats" in features


def test_vectorize_is_ndarray(extractor):
    vec = extractor.vectorize("Texto qualquer.")
    assert isinstance(vec, np.ndarray)
    assert vec.ndim == 1


def test_vectorize_length_matches_feature_names(extractor):
    vec = extractor.vectorize("Texto qualquer.")
    assert len(vec) == len(extractor.feature_names)


def test_vectorize_batch_shape(extractor):
    texts = ["Texto A.", "Texto B.", "Texto C."]
    X = extractor.vectorize_batch(texts)
    assert X.shape == (3, len(extractor.feature_names))


# ---------------------------------------------------------------------------
# FeatureExtractor — padrões clínicos
# ---------------------------------------------------------------------------

def test_sexual_violence_pattern(extractor):
    features = extractor.extract("Paciente relata estupro pelo companheiro.")
    assert features["pattern_flags"]["sexual_violence"] is True


def test_self_harm_pattern(extractor):
    features = extractor.extract("Ideação suicida e tentativa de autolesão.")
    assert features["pattern_flags"]["self_harm"] is True


def test_neglect_pattern(extractor):
    features = extractor.extract("Criança com negligência grave e desnutrição.")
    assert features["pattern_flags"]["neglect"] is True


def test_weapons_pattern(extractor):
    features = extractor.extract("Agredida com arma branca pelo parceiro.")
    assert features["pattern_flags"]["weapons_involved"] is True


def test_no_patterns_neutral_text(extractor):
    features = extractor.extract("Paciente com febre e tosse há três dias.")
    assert not any(features["pattern_flags"].values())


def test_total_score_positive_for_violent_text(extractor):
    features = extractor.extract("Vítima de espancamento com lesão corporal.")
    assert features["total_score"] > 0.0


def test_negated_count_increments(extractor):
    features = extractor.extract("Paciente nega violência doméstica.")
    assert features["negated_count"] >= 1


def test_text_stats_word_count(extractor):
    text = "Uma frase com quatro palavras."
    features = extractor.extract(text)
    assert features["text_stats"]["word_count"] == len(text.split())


# ---------------------------------------------------------------------------
# NotificationClassifier — modo regras
# ---------------------------------------------------------------------------

def test_predict_returns_type_and_confidence(clf):
    ntype, conf = clf.predict("Paciente com lesão corporal.")
    assert isinstance(ntype, NotificationType)
    assert 0.0 <= conf <= 1.0


def test_predict_sexual_violence_by_rules(clf):
    ntype, _ = clf.predict("Vítima de estupro pelo marido.")
    assert ntype == NotificationType.VIOLENCIA_SEXUAL


def test_predict_self_harm_by_rules(clf):
    ntype, _ = clf.predict("Paciente com ideação suicida e tentativa de suicídio.")
    assert ntype == NotificationType.VIOLENCIA_AUTOPROVOCADA


def test_predict_neglect_by_rules(clf):
    ntype, _ = clf.predict("Criança com negligência grave e abandono de incapaz.")
    assert ntype == NotificationType.NEGLIGENCIA


def test_predict_neutral_text_returns_outros(clf):
    ntype, _ = clf.predict("Consulta de rotina. Sem queixas.")
    assert ntype == NotificationType.OUTROS


def test_predict_proba_all_types_covered(clf):
    proba = clf.predict_proba("Paciente com violência doméstica e lesão corporal.")
    for ntype in NotificationType:
        assert ntype in proba


def test_predict_proba_sums_to_approx_one(clf):
    proba = clf.predict_proba("Espancamento com fratura de costela.")
    assert abs(sum(proba.values()) - 1.0) < 1e-3


def test_is_trained_false_initially(clf):
    assert clf.is_trained is False


def test_fit_raises_without_sklearn():
    if HAS_SKLEARN:
        pytest.skip("scikit-learn disponível; teste não se aplica.")
    from classifier import NotificationClassifier as NC
    nc = NC()
    with pytest.raises(ImportError):
        nc.fit(["texto"], [NotificationType.VIOLENCIA_FISICA])


def test_fit_raises_on_size_mismatch():
    clf_local = NotificationClassifier()
    with pytest.raises(ValueError):
        clf_local.fit(["texto1", "texto2"], [NotificationType.VIOLENCIA_FISICA])


# ---------------------------------------------------------------------------
# NotificationClassifier — modo ML (requer scikit-learn)
# ---------------------------------------------------------------------------

SYNTHETIC_TEXTS = [
    "Paciente com estupro e violência sexual grave.",
    "Vítima de estupro pelo companheiro.",
    "Sexo forçado relatado pela paciente.",
    "Ideação suicida com tentativa de autolesão.",
    "Tentativa de suicídio com automutilação.",
    "Comportamento autodestrutivo e autoextermínio.",
    "Lesão corporal e espancamento pelo parceiro.",
    "Violência física com hematomas múltiplos.",
    "Agressão com fraturas e trauma contundente.",
    "Criança com negligência grave e desnutrição.",
    "Abandono de incapaz e falta de higiene.",
]
SYNTHETIC_LABELS = [
    NotificationType.VIOLENCIA_SEXUAL,
    NotificationType.VIOLENCIA_SEXUAL,
    NotificationType.VIOLENCIA_SEXUAL,
    NotificationType.VIOLENCIA_AUTOPROVOCADA,
    NotificationType.VIOLENCIA_AUTOPROVOCADA,
    NotificationType.VIOLENCIA_AUTOPROVOCADA,
    NotificationType.VIOLENCIA_FISICA,
    NotificationType.VIOLENCIA_FISICA,
    NotificationType.VIOLENCIA_FISICA,
    NotificationType.NEGLIGENCIA,
    NotificationType.NEGLIGENCIA,
]


@pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn não instalado")
def test_fit_sets_is_trained():
    clf_ml = NotificationClassifier()
    clf_ml.fit(SYNTHETIC_TEXTS, SYNTHETIC_LABELS)
    assert clf_ml.is_trained is True


@pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn não instalado")
def test_ml_predict_returns_valid_type():
    clf_ml = NotificationClassifier()
    clf_ml.fit(SYNTHETIC_TEXTS, SYNTHETIC_LABELS)
    ntype, conf = clf_ml.predict("Paciente vítima de estupro.")
    assert isinstance(ntype, NotificationType)
    assert 0.0 <= conf <= 1.0


@pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn não instalado")
def test_ml_predict_proba_sums_to_one(tmp_path):
    clf_ml = NotificationClassifier()
    clf_ml.fit(SYNTHETIC_TEXTS, SYNTHETIC_LABELS)
    proba = clf_ml.predict_proba("Espancamento com lesão corporal.")
    assert abs(sum(proba.values()) - 1.0) < 1e-3


@pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn não instalado")
def test_save_and_load(tmp_path):
    clf_ml = NotificationClassifier()
    clf_ml.fit(SYNTHETIC_TEXTS, SYNTHETIC_LABELS)
    model_path = str(tmp_path / "modelo_teste.pkl")
    clf_ml.save(model_path)

    loaded = NotificationClassifier.load(model_path)
    assert loaded.is_trained
    ntype, conf = loaded.predict("Vítima de estupro.")
    assert isinstance(ntype, NotificationType)


# ---------------------------------------------------------------------------
# AnalysisPipeline
# ---------------------------------------------------------------------------

def test_pipeline_returns_all_keys(pipeline):
    result = pipeline.analyze_text("Paciente com violência doméstica e lesão corporal.")
    expected = {
        "detections", "score", "features", "notification_type",
        "confidence", "all_probabilities", "mode", "processing_ms",
    }
    assert expected.issubset(result.keys())


def test_pipeline_mode_is_rules(pipeline):
    result = pipeline.analyze_text("Texto qualquer.")
    assert result["mode"] == "rules"


def test_pipeline_score_positive_for_violent_text(pipeline):
    result = pipeline.analyze_text("Espancamento com fraturas múltiplas e estupro.")
    assert result["score"] > 0


def test_pipeline_score_zero_for_neutral_text(pipeline):
    result = pipeline.analyze_text("Consulta preventiva sem queixas.")
    assert result["score"] == 0.0


def test_pipeline_notification_type_is_enum(pipeline):
    result = pipeline.analyze_text("Paciente com ideação suicida.")
    assert isinstance(result["notification_type"], NotificationType)


def test_pipeline_all_proba_covers_all_types(pipeline):
    result = pipeline.analyze_text("Paciente com violência psicológica.")
    for ntype in NotificationType:
        assert ntype in result["all_probabilities"]


def test_pipeline_summary_returns_string(pipeline):
    result = pipeline.analyze_text("Paciente com lesão corporal.")
    summary = pipeline.summary(result)
    assert isinstance(summary, str)
    assert "notificação" in summary.lower()


def test_pipeline_analyze_batch(pipeline):
    texts = ["Violência doméstica.", "Febre e tosse.", "Estupro pelo parceiro."]
    results = pipeline.analyze_batch(texts)
    assert len(results) == 3
    assert all("notification_type" in r for r in results)


def test_pipeline_processing_ms_nonnegative(pipeline):
    result = pipeline.analyze_text("Texto simples.")
    assert result["processing_ms"] >= 0
