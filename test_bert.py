"""
Testes para BertEmbedder, ClinicalNER e integrações BERT no pipeline.

Os testes que exigem torch/transformers são marcados com
@pytest.mark.skipif(not HAS_TRANSFORMERS, ...) e são ignorados
quando as dependências não estão instaladas.

Testes de carregamento real de modelo (download da internet) são marcados
com @pytest.mark.slow e ignorados por padrão. Para executá-los:
    pytest test_bert.py -m slow
"""

import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

# ---------------------------------------------------------------------------
# Detectar disponibilidade de dependências opcionais
# ---------------------------------------------------------------------------
try:
    import torch
    import transformers
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

# ---------------------------------------------------------------------------
# Testes de BertEmbedder (estrutura / sem modelo real)
# ---------------------------------------------------------------------------


def test_embedder_import_error_without_transformers(monkeypatch):
    """BertEmbedder levanta ImportError quando transformers não está disponível."""
    import embedder as emb_module
    original = emb_module.HAS_TRANSFORMERS
    monkeypatch.setattr(emb_module, "HAS_TRANSFORMERS", False)
    try:
        with pytest.raises(ImportError, match="torch"):
            emb_module.BertEmbedder("qualquer-modelo")
    finally:
        monkeypatch.setattr(emb_module, "HAS_TRANSFORMERS", original)


def test_make_embedder_returns_none_without_transformers(monkeypatch):
    """make_embedder retorna None quando transformers não está disponível."""
    import embedder as emb_module
    original = emb_module.HAS_TRANSFORMERS
    monkeypatch.setattr(emb_module, "HAS_TRANSFORMERS", False)
    try:
        result = emb_module.make_embedder()
        assert result is None
    finally:
        monkeypatch.setattr(emb_module, "HAS_TRANSFORMERS", original)


def test_mean_pool_shape():
    """_mean_pool retorna shape correto."""
    if not HAS_TRANSFORMERS:
        pytest.skip("torch não disponível")
    import torch
    from embedder import _mean_pool
    hidden = torch.randn(2, 10, 768)
    mask = torch.ones(2, 10)
    result = _mean_pool(hidden, mask)
    assert result.shape == (2, 768)


def test_mean_pool_ignores_padding():
    """_mean_pool ignora tokens de padding (mask=0)."""
    if not HAS_TRANSFORMERS:
        pytest.skip("torch não disponível")
    import torch
    from embedder import _mean_pool
    # Dois textos idênticos, mas o segundo com metade do padding mascarado
    hidden = torch.ones(2, 4, 8)
    mask_full = torch.ones(2, 4)
    mask_partial = torch.tensor([[1, 1, 0, 0], [1, 1, 0, 0]], dtype=torch.float)
    result_full = _mean_pool(hidden, mask_full)
    result_partial = _mean_pool(hidden, mask_partial)
    # Ambos devem ser iguais pois os valores são 1.0 em todos os tokens reais
    np.testing.assert_allclose(result_full, result_partial, atol=1e-5)


def test_l2_normalize():
    """_l2_normalize produz vetores com norma unitária."""
    from embedder import _l2_normalize
    matrix = np.array([[3.0, 4.0], [1.0, 0.0], [0.0, 0.0]])
    normed = _l2_normalize(matrix)
    # Linha com norma > 0 deve ter norma 1
    assert abs(np.linalg.norm(normed[0]) - 1.0) < 1e-6
    assert abs(np.linalg.norm(normed[1]) - 1.0) < 1e-6
    # Linha zero deve permanecer zero (sem divisão por zero)
    np.testing.assert_array_equal(normed[2], [0.0, 0.0])


# ---------------------------------------------------------------------------
# Testes de ClinicalNER (estrutura / sem modelo real)
# ---------------------------------------------------------------------------


def test_ner_import_error_without_transformers(monkeypatch):
    """ClinicalNER levanta ImportError quando transformers não está disponível."""
    import ner as ner_module
    original = ner_module.HAS_TRANSFORMERS
    monkeypatch.setattr(ner_module, "HAS_TRANSFORMERS", False)
    try:
        with pytest.raises(ImportError, match="transformers"):
            ner_module.ClinicalNER()
    finally:
        monkeypatch.setattr(ner_module, "HAS_TRANSFORMERS", original)


def test_ner_model_ids_are_valid():
    """Todos os model IDs de CLINICALNER_MODELS são strings não-vazias."""
    from ner import CLINICALNER_MODELS
    for key, model_id in CLINICALNER_MODELS.items():
        assert isinstance(model_id, str) and model_id.startswith("pucpr/"), (
            f"Model ID inválido para '{key}': {model_id!r}"
        )


def test_ner_violence_patterns_list():
    """VIOLENCE_RELATED_ENTITY_PATTERNS contém termos relevantes."""
    from ner import VIOLENCE_RELATED_ENTITY_PATTERNS
    assert "trauma" in VIOLENCE_RELATED_ENTITY_PATTERNS
    assert "violência" in VIOLENCE_RELATED_ENTITY_PATTERNS
    assert "abuso" in VIOLENCE_RELATED_ENTITY_PATTERNS


def test_is_violence_related():
    """_is_violence_related detecta termos relevantes."""
    from ner import _is_violence_related
    assert _is_violence_related("trauma crânio-encefálico") is True
    assert _is_violence_related("hematoma subdural") is True
    assert _is_violence_related("automutilação") is True
    assert _is_violence_related("hipertensão arterial") is False
    assert _is_violence_related("diabetes tipo 2") is False


def test_clinical_entity_dataclass():
    """ClinicalEntity pode ser instanciado corretamente."""
    from ner import ClinicalEntity
    entity = ClinicalEntity(
        text="trauma cranioencefálico",
        label="Disease_or_Syndrome",
        score=0.95,
        start=10,
        end=33,
        ner_model="disease",
        violence_related=True,
    )
    assert entity.text == "trauma cranioencefálico"
    assert entity.violence_related is True
    assert 0 <= entity.score <= 1


def test_ner_result_dataclass():
    """NERResult é inicializado com valores padrão corretos."""
    from ner import NERResult
    result = NERResult()
    assert result.entities == []
    assert result.violence_entity_count == 0
    assert result.violence_entity_score == 0.0


# ---------------------------------------------------------------------------
# Testes de FeatureExtractor com e sem embedder
# ---------------------------------------------------------------------------


def test_feature_extractor_no_bert_feature_names():
    """FeatureExtractor sem BERT tem nomes sem prefixo bert_."""
    from features import FeatureExtractor
    extractor = FeatureExtractor()
    assert not any(n.startswith("bert_") for n in extractor.feature_names)
    assert extractor.uses_bert is False


def test_feature_extractor_with_mock_bert(monkeypatch):
    """FeatureExtractor com embedder stub concatena embedding ao vetor."""
    import numpy as np
    from features import FeatureExtractor

    # Stub de BertEmbedder sem carregar modelo real
    class MockEmbedder:
        model_id = "mock/model"
        embedding_dim = 4

        def embed(self, text):
            return np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

        def embed_batch(self, texts):
            return np.tile([0.1, 0.2, 0.3, 0.4], (len(texts), 1)).astype(np.float32)

    extractor = FeatureExtractor(embedder=MockEmbedder())
    assert extractor.uses_bert is True

    # feature_names deve incluir bert_0 … bert_3
    names = extractor.feature_names
    assert "bert_0" in names
    assert "bert_3" in names

    # vetor deve ter comprimento = lexical + 4
    vec = extractor.vectorize("Paciente com lesão corporal.")
    lexical_only = FeatureExtractor()
    lexical_vec = lexical_only.vectorize("Paciente com lesão corporal.")
    assert len(vec) == len(lexical_vec) + 4


def test_feature_extractor_batch_with_mock_bert():
    """vectorize_batch com embedder stub retorna shape correto."""
    import numpy as np
    from features import FeatureExtractor

    class MockEmbedder:
        model_id = "mock/model"
        embedding_dim = 8

        def embed(self, text):
            return np.zeros(8, dtype=np.float32)

        def embed_batch(self, texts):
            return np.zeros((len(texts), 8), dtype=np.float32)

    extractor = FeatureExtractor(embedder=MockEmbedder())
    lexical_dim = len(FeatureExtractor().feature_names)
    X = extractor.vectorize_batch(["texto A", "texto B", "texto C"])
    assert X.shape == (3, lexical_dim + 8)


# ---------------------------------------------------------------------------
# Testes de NotificationClassifier com embedder stub
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not __import__("importlib").util.find_spec("sklearn"),
                    reason="scikit-learn não instalado")
def test_classifier_fit_with_mock_bert():
    """NotificationClassifier treina corretamente com extractor BERT stub."""
    import numpy as np
    from features import FeatureExtractor
    from classifier import NotificationClassifier
    from notification_types import NotificationType

    class MockEmbedder:
        model_id = "mock/model"
        embedding_dim = 4

        def embed(self, text):
            return np.random.rand(4).astype(np.float32)

        def embed_batch(self, texts):
            return np.random.rand(len(texts), 4).astype(np.float32)

    extractor = FeatureExtractor(embedder=MockEmbedder())
    clf = NotificationClassifier(extractor=extractor)

    texts = [
        "Paciente vítima de estupro.",
        "Vítima de estupro pelo marido.",
        "Ideação suicida e autolesão.",
        "Tentativa de suicídio.",
        "Lesão corporal e espancamento.",
        "Hematomas múltiplos e fratura.",
    ]
    labels = [
        NotificationType.VIOLENCIA_SEXUAL,
        NotificationType.VIOLENCIA_SEXUAL,
        NotificationType.VIOLENCIA_AUTOPROVOCADA,
        NotificationType.VIOLENCIA_AUTOPROVOCADA,
        NotificationType.VIOLENCIA_FISICA,
        NotificationType.VIOLENCIA_FISICA,
    ]
    clf.fit(texts, labels)
    assert clf.is_trained

    ntype, conf = clf.predict("Paciente relata estupro.")
    assert isinstance(ntype, NotificationType)
    assert 0.0 <= conf <= 1.0


# ---------------------------------------------------------------------------
# Testes de AnalysisPipeline com NER stub
# ---------------------------------------------------------------------------


def test_pipeline_with_ner_stub():
    """AnalysisPipeline inclui ner_result quando NER está configurado."""
    from pipeline import AnalysisPipeline
    from ner import NERResult, ClinicalEntity

    class MockNER:
        def analyze(self, text):
            result = NERResult(models_used=["mock"])
            result.entities = [
                ClinicalEntity(
                    text="trauma",
                    label="Disease",
                    score=0.9,
                    start=0,
                    end=6,
                    ner_model="mock",
                    violence_related=True,
                )
            ]
            result.violence_entity_count = 1
            result.violence_entity_score = 0.9
            return result

    pipeline = AnalysisPipeline(ner=MockNER())
    result = pipeline.analyze_text("trauma cranioencefálico")

    assert result["ner_result"] is not None
    assert result["ner_result"].violence_entity_count == 1
    assert result["ner_result"].violence_entity_score == pytest.approx(0.9)


def test_pipeline_ner_none_by_default():
    """AnalysisPipeline sem NER retorna ner_result=None."""
    from pipeline import AnalysisPipeline
    pipeline = AnalysisPipeline()
    result = pipeline.analyze_text("Texto qualquer.")
    assert result["ner_result"] is None


def test_pipeline_mode_ml_bert_label():
    """Pipeline com extractor BERT e modelo treinado usa label 'ml+bert'."""
    import numpy as np
    from features import FeatureExtractor
    from classifier import NotificationClassifier
    from pipeline import AnalysisPipeline
    from notification_types import NotificationType

    try:
        import sklearn  # noqa
    except ImportError:
        pytest.skip("scikit-learn não disponível")

    class MockEmbedder:
        model_id = "mock/model"
        embedding_dim = 4

        def embed(self, text):
            return np.random.rand(4).astype(np.float32)

        def embed_batch(self, texts):
            return np.random.rand(len(texts), 4).astype(np.float32)

    extractor = FeatureExtractor(embedder=MockEmbedder())
    texts = [
        "Paciente vítima de estupro.",
        "Lesão corporal e espancamento.",
        "Ideação suicida.",
        "Vítima de estupro.",
        "Hematoma múltiplo.",
        "Tentativa de autolesão.",
    ]
    labels = [
        NotificationType.VIOLENCIA_SEXUAL,
        NotificationType.VIOLENCIA_FISICA,
        NotificationType.VIOLENCIA_AUTOPROVOCADA,
        NotificationType.VIOLENCIA_SEXUAL,
        NotificationType.VIOLENCIA_FISICA,
        NotificationType.VIOLENCIA_AUTOPROVOCADA,
    ]
    clf = NotificationClassifier(extractor=extractor)
    clf.fit(texts, labels)

    pipeline = AnalysisPipeline(extractor=extractor)
    pipeline._classifier = clf

    result = pipeline.analyze_text("Paciente com lesão corporal.")
    assert result["mode"] == "ml+bert"


def test_pipeline_summary_includes_ner():
    """summary() inclui linha de entidades clínicas quando NER ativo."""
    from pipeline import AnalysisPipeline
    from ner import NERResult, ClinicalEntity

    class MockNER:
        def analyze(self, text):
            r = NERResult(models_used=["mock"])
            r.violence_entity_count = 2
            r.violence_entity_score = 1.8
            r.entities = []
            return r

    pipeline = AnalysisPipeline(ner=MockNER())
    result = pipeline.analyze_text("Paciente com trauma.")
    summary = pipeline.summary(result)
    assert "Entidades clínicas" in summary
    assert "2" in summary


# ---------------------------------------------------------------------------
# Testes de carregamento real (marcados como slow — requerem internet)
# ---------------------------------------------------------------------------

@pytest.mark.slow
@pytest.mark.skipif(not HAS_TRANSFORMERS, reason="torch/transformers não instalados")
def test_bertembedder_real_biobertpt():
    """Carrega biobertpt-clin real e extrai embedding de forma correta."""
    from embedder import BertEmbedder
    embedder = BertEmbedder("pucpr/biobertpt-clin", device="cpu")
    vec = embedder.embed("Paciente apresenta hematoma periorbital.")
    assert vec.shape == (768,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-4  # L2-normalizado


@pytest.mark.slow
@pytest.mark.skipif(not HAS_TRANSFORMERS, reason="torch/transformers não instalados")
def test_bertembedder_real_bertimbau():
    """Carrega BERTimbau real e extrai embedding."""
    from embedder import BertEmbedder
    embedder = BertEmbedder(
        "neuralmind/bert-base-portuguese-cased", device="cpu"
    )
    vec = embedder.embed("Paciente relata agressão física.")
    assert vec.shape == (768,)


@pytest.mark.slow
@pytest.mark.skipif(not HAS_TRANSFORMERS, reason="torch/transformers não instalados")
def test_clinical_ner_real_disease():
    """ClinicalNER com clinicalnerpt-disease retorna entidades."""
    from ner import ClinicalNER
    ner = ClinicalNER(models=["disease"], device=-1)
    result = ner.analyze(
        "Paciente com diagnóstico de trauma cranioencefálico e hematoma subdural."
    )
    assert len(result.entities) > 0
    assert all(0 <= e.score <= 1 for e in result.entities)
    assert result.violence_entity_count > 0
