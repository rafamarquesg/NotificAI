"""
NER clínico em português usando modelos pucpr/clinicalnerpt-*.

Os modelos são variantes do BioBERTpt fine-tuned no corpus SemClinBr
(prontuários do Hospital das Clínicas - USP) com anotações UMLS em
formato IOB2. Cada modelo é especializado em um tipo de entidade.

Modelos disponíveis:
    pucpr/clinicalnerpt-disease      — Doenças e diagnósticos
    pucpr/clinicalnerpt-medical      — Conceitos médicos gerais
    pucpr/clinicalnerpt-procedure    — Procedimentos clínicos
    pucpr/clinicalnerpt-therapeutic  — Intervenções terapêuticas
    pucpr/clinicalnerpt-healthcare   — Entidades de saúde

Para detecção de violência, as entidades mais relevantes são:
  - disease:    diagnósticos de lesão, trauma, TEPT, depressão, etc.
  - medical:    termos médicos gerais que indicam agressão
  - therapeutic: tratamentos que surgem após episódios de violência

Referência:
    Schneider, E. et al. BioBERTpt — A Portuguese Neural Language Model
    for Clinical NER. ACL Clinical NLP Workshop, 2020.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Importações opcionais
# ---------------------------------------------------------------------------
try:
    from transformers import pipeline, Pipeline

    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

#: Modelos clinicalnerpt disponíveis e suas descrições.
CLINICALNER_MODELS: Dict[str, str] = {
    "medical":      "pucpr/clinicalnerpt-medical",      # todos os 13 tipos UMLS
    "disease":      "pucpr/clinicalnerpt-disease",      # doenças / diagnósticos
    "chemical":     "pucpr/clinicalnerpt-chemical",     # medicamentos / substâncias
    "procedure":    "pucpr/clinicalnerpt-procedure",    # procedimentos médicos
    "diagnostic":   "pucpr/clinicalnerpt-diagnostic",   # procedimentos diagnósticos
    "therapeutic":  "pucpr/clinicalnerpt-therapeutic",  # intervenções terapêuticas
    "healthcare":   "pucpr/clinicalnerpt-healthcare",   # atividades de saúde
    "laboratory":   "pucpr/clinicalnerpt-laboratory",   # resultados laboratoriais
    "quantitative": "pucpr/clinicalnerpt-quantitative", # conceitos quantitativos
}

#: Subconjunto de modelos mais úteis para detecção de violência.
#: "disease" captura lesões/diagnósticos; "medical" cobre 13 tipos UMLS.
VIOLENCE_RELEVANT_NER = ("disease", "medical")

#: Entidades clínicas que têm alta correlação com violência.
VIOLENCE_RELATED_ENTITY_PATTERNS = [
    # Trauma e lesões
    "trauma", "lesão", "fratura", "hematoma", "equimose", "laceração",
    "ferimento", "escoriação", "queimadura", "contusão",
    # Saúde mental pós-violência
    "estresse", "ansiedade", "depressão", "dissociação", "flashback",
    "automutilação", "suicídio", "autolesão",
    # Condições específicas de abuso
    "abuso", "negligência", "violência", "agressão",
]


# ---------------------------------------------------------------------------
# Modelos de dados
# ---------------------------------------------------------------------------

@dataclass
class ClinicalEntity:
    """Entidade clínica reconhecida pelo NER."""
    text: str
    label: str           # rótulo UMLS (ex.: "Disease_or_Syndrome")
    score: float         # confiança do modelo (0-1)
    start: int           # posição inicial no texto original
    end: int             # posição final no texto original
    ner_model: str       # modelo que detectou a entidade
    violence_related: bool = False  # se é relevante para violência


@dataclass
class NERResult:
    """Resultado completo de NER para um texto."""
    entities: List[ClinicalEntity] = field(default_factory=list)
    violence_entity_count: int = 0
    violence_entity_score: float = 0.0   # soma das confianças de entidades relevantes
    models_used: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class ClinicalNER:
    """
    Reconhecimento de Entidades Nomeadas (NER) em textos clínicos portugueses.

    Usa os modelos pucpr/clinicalnerpt-* (BioBERTpt fine-tuned no SemClinBr).
    Suporta uso de um único modelo ou combinação de múltiplos para maior recall.

    Uso básico (modelo de doenças):
        ner = ClinicalNER()
        result = ner.analyze("Paciente com trauma cranioencefálico.")
        for entity in result.entities:
            print(entity.text, entity.label, entity.score)

    Uso com múltiplos modelos:
        ner = ClinicalNER(models=["disease", "medical"])
        result = ner.analyze(texto)

    Raises:
        ImportError: se transformers não estiver instalado.
    """

    def __init__(
        self,
        models: Optional[List[str]] = None,
        device: int = -1,
        aggregation_strategy: str = "simple",
        min_score: float = 0.70,
    ) -> None:
        """
        Args:
            models:               lista de chaves de CLINICALNER_MODELS a usar.
                                  Padrão: ["disease", "medical"].
            device:               -1 para CPU, 0+ para GPU (índice CUDA).
            aggregation_strategy: como agrupar sub-tokens ("simple", "first", "max").
            min_score:            descarta entidades com confiança abaixo deste limiar.
        """
        if not HAS_TRANSFORMERS:
            raise ImportError(
                "transformers é necessário para ClinicalNER.\n"
                "Execute: pip install transformers"
            )

        self.min_score = min_score
        self.aggregation_strategy = aggregation_strategy
        self._pipes: Dict[str, "Pipeline"] = {}

        model_keys = models if models is not None else list(VIOLENCE_RELEVANT_NER)

        for key in model_keys:
            model_id = CLINICALNER_MODELS.get(key)
            if model_id is None:
                logger.warning("Modelo NER desconhecido: '%s'. Ignorando.", key)
                continue
            try:
                logger.info("Carregando NER '%s' (%s)…", key, model_id)
                self._pipes[key] = pipeline(
                    "token-classification",
                    model=model_id,
                    aggregation_strategy=aggregation_strategy,
                    device=device,
                )
                logger.info("NER '%s' carregado.", key)
            except Exception as exc:
                logger.warning("Falha ao carregar NER '%s': %s", key, exc)

        if not self._pipes:
            raise RuntimeError(
                "Nenhum modelo NER pôde ser carregado. "
                "Verifique a sua conexão ou os nomes dos modelos."
            )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def analyze(self, text: str) -> NERResult:
        """
        Executa NER no texto e retorna entidades detectadas.

        Entidades com `score < min_score` são descartadas.
        Entidades cujo texto contém termos relacionados à violência
        recebem `violence_related = True`.

        Args:
            text: texto clínico em português.

        Returns:
            NERResult com lista de entidades e métricas agregadas.
        """
        result = NERResult(models_used=list(self._pipes.keys()))
        seen_spans = set()  # (start, end) para evitar duplicatas entre modelos

        for ner_key, pipe in self._pipes.items():
            try:
                raw = pipe(text)
            except Exception as exc:
                logger.warning("Erro ao executar NER '%s': %s", ner_key, exc)
                continue

            for item in raw:
                score = float(item.get("score", 0.0))
                if score < self.min_score:
                    continue

                start = int(item.get("start", 0))
                end = int(item.get("end", 0))
                span = (start, end)

                if span in seen_spans:
                    continue
                seen_spans.add(span)

                entity_text = item.get("word", text[start:end]).strip()
                label = item.get("entity_group", item.get("entity", "UNK"))
                violence_rel = _is_violence_related(entity_text)

                entity = ClinicalEntity(
                    text=entity_text,
                    label=label,
                    score=round(score, 4),
                    start=start,
                    end=end,
                    ner_model=ner_key,
                    violence_related=violence_rel,
                )
                result.entities.append(entity)

        # Agregar métricas de violência
        viol_entities = [e for e in result.entities if e.violence_related]
        result.violence_entity_count = len(viol_entities)
        result.violence_entity_score = round(
            sum(e.score for e in viol_entities), 4
        )

        return result

    def to_features(self, ner_result: NERResult) -> Dict[str, float]:
        """
        Converte um NERResult em features numéricas para uso em ML.

        Retorna dicionário com:
          - ner_total_entities:    número total de entidades detectadas
          - ner_violence_count:    entidades relacionadas à violência
          - ner_violence_score:    soma de confiança das entidades de violência
          - ner_<tipo>_count:      contagem por tipo de entidade NER
        """
        features: Dict[str, float] = {
            "ner_total_entities": float(len(ner_result.entities)),
            "ner_violence_count": float(ner_result.violence_entity_count),
            "ner_violence_score": ner_result.violence_entity_score,
        }
        # Contagem por modelo (ex.: ner_disease_count, ner_medical_count)
        for key in self._pipes:
            features[f"ner_{key}_count"] = float(
                sum(1 for e in ner_result.entities if e.ner_model == key)
            )
        return features

    @property
    def loaded_models(self) -> List[str]:
        """Chaves dos modelos NER carregados com sucesso."""
        return list(self._pipes.keys())


# ---------------------------------------------------------------------------
# Utilitários internos
# ---------------------------------------------------------------------------

def _is_violence_related(entity_text: str) -> bool:
    """Verifica se o texto de uma entidade está associado à violência."""
    text_lower = entity_text.lower()
    return any(pattern in text_lower for pattern in VIOLENCE_RELATED_ENTITY_PATTERNS)
