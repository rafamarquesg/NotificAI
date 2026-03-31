"""
Pipeline de análise completo: texto → detecção → NER → características → classificação.

Integra todos os módulos do sistema NUVE em uma única interface de entrada.
Suporta três níveis de riqueza, ativados conforme as dependências disponíveis:

  Nível 1 — Lexical (padrão, sem GPU):
    ViolenceDetector + FeatureExtractor lexical + NotificationClassifier (regras/ML)

  Nível 2 — Lexical + NER clínico (requer transformers):
    Nível 1 + ClinicalNER (pucpr/clinicalnerpt-disease, clinicalnerpt-medical)

  Nível 3 — Lexical + NER + BERT (requer transformers + torch):
    Nível 2 + BertEmbedder (pucpr/biobertpt-clin ou BERTimbau) concatenado
    às características lexicais antes da classificação.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .detector import ViolenceDetector
    from .features import FeatureExtractor
    from .classifier import NotificationClassifier
    from .notification_types import NotificationType
except ImportError:
    from detector import ViolenceDetector
    from features import FeatureExtractor
    from classifier import NotificationClassifier
    from notification_types import NotificationType

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """
    Orquestra a análise completa de texto para detecção de violência e
    classificação do tipo de notificação.

    Uso — Nível 1 (só regras, sem dependências extras):
        pipeline = AnalysisPipeline()
        result = pipeline.analyze_text("Paciente vítima de violência doméstica.")
        print(pipeline.summary(result))

    Uso — Nível 2 (+ NER clínico, requer transformers):
        from ner import ClinicalNER
        pipeline = AnalysisPipeline(ner=ClinicalNER())
        result = pipeline.analyze_text(texto)

    Uso — Nível 3 (+ BERT embeddings, requer torch + transformers):
        from embedder import BertEmbedder
        from features import FeatureExtractor
        embedder = BertEmbedder("pucpr/biobertpt-clin")
        extractor = FeatureExtractor(embedder=embedder)
        pipeline = AnalysisPipeline(
            extractor=extractor,
            ner=ClinicalNER(),
        )
        result = pipeline.analyze_text(texto)

    Uso — Carregar modelo treinado:
        pipeline = AnalysisPipeline(model_path="modelo_nuve.pkl")
        result = pipeline.analyze_text(texto)

    Treinamento (quando dados rotulados estiverem disponíveis):
        pipeline = AnalysisPipeline(extractor=extractor)
        pipeline.classifier.fit(texts, labels)
        pipeline.classifier.save("modelo_nuve.pkl")
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        extractor: Optional["FeatureExtractor"] = None,
        ner: Optional[Any] = None,
    ) -> None:
        """
        Args:
            model_path: caminho para um modelo .pkl salvo (opcional).
                        Se não existir, opera no modo regras.
            extractor:  FeatureExtractor personalizado (opcional).
                        Passe um com BertEmbedder para habilitar embeddings BERT.
            ner:        instância de ClinicalNER (opcional).
                        Quando fornecida, resultados de NER são incluídos
                        na saída de analyze_text.
        """
        self._detector = ViolenceDetector()
        self._extractor = extractor if extractor is not None else FeatureExtractor()
        self._ner = ner

        if model_path and Path(model_path).exists():
            logger.info("Carregando modelo ML de: %s", model_path)
            self._classifier = NotificationClassifier.load(model_path)
        else:
            if model_path:
                logger.warning(
                    "Modelo não encontrado em '%s'. Usando modo regras.", model_path
                )
            self._classifier = NotificationClassifier(extractor=self._extractor)

    # ------------------------------------------------------------------
    # Análise
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analisa um texto e retorna um dicionário com todos os resultados.

        Retorno:
            {
              "detections":        List[dict]        — termos lexicais detectados,
              "score":             float             — pontuação total (sem negados),
              "features":          dict              — características interpretáveis,
              "ner_result":        NERResult | None  — entidades clínicas (se NER ativo),
              "notification_type": NotificationType  — tipo de notificação inferido,
              "confidence":        float [0, 1]      — confiança da classificação,
              "all_probabilities": Dict[NotificationType, float],
              "mode":              str               — "rules", "ml" ou "ml+bert",
              "processing_ms":     float             — tempo de processamento,
            }
        """
        start = time.perf_counter()

        detections = self._detector.analyze(text)
        score = sum(d["weight"] for d in detections if not d["negated"])
        features = self._extractor.extract(text)
        ntype, confidence = self._classifier.predict(text)
        all_proba = self._classifier.predict_proba(text)

        # NER clínico (opcional)
        ner_result = None
        if self._ner is not None:
            try:
                ner_result = self._ner.analyze(text)
            except Exception as exc:
                logger.warning("Erro no NER clínico: %s", exc)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "detections": detections,
            "score": round(score, 3),
            "features": features,
            "ner_result": ner_result,
            "notification_type": ntype,
            "confidence": confidence,
            "all_probabilities": all_proba,
            "mode": self._mode_label(),
            "processing_ms": elapsed_ms,
        }

    def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Analisa uma lista de textos. Útil para processamento em lote."""
        return [self.analyze_text(t) for t in texts]

    def summary(self, result: Dict[str, Any]) -> str:
        """Gera um resumo legível de um resultado de `analyze_text`."""
        lines = [
            f"Tipo de notificação : {result['notification_type'].value}",
            f"Confiança           : {result['confidence']:.1%}",
            f"Pontuação total     : {result['score']:.2f}",
            f"Modo                : {result['mode'].upper()}",
            f"Termos detectados   : {len(result['detections'])} "
            f"({sum(1 for d in result['detections'] if d['negated'])} negados)",
            f"Tempo               : {result['processing_ms']} ms",
        ]
        active_patterns = [
            k for k, v in result["features"]["pattern_flags"].items() if v
        ]
        if active_patterns:
            lines.append(f"Padrões ativos      : {', '.join(active_patterns)}")

        ner = result.get("ner_result")
        if ner is not None:
            lines.append(
                f"Entidades clínicas  : {len(ner.entities)} total, "
                f"{ner.violence_entity_count} relacionadas à violência"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Acesso aos componentes
    # ------------------------------------------------------------------

    @property
    def classifier(self) -> NotificationClassifier:
        """Acesso direto ao classificador (para fit/save/load)."""
        return self._classifier

    @property
    def detector(self) -> ViolenceDetector:
        """Acesso direto ao detector lexical."""
        return self._detector

    @property
    def extractor(self) -> FeatureExtractor:
        """Acesso direto ao extrator de características."""
        return self._extractor

    @property
    def ner(self) -> Optional[Any]:
        """Acesso direto ao ClinicalNER (None se não configurado)."""
        return self._ner

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _mode_label(self) -> str:
        if not self._classifier.is_trained:
            return "rules"
        if self._extractor.uses_bert:
            return "ml+bert"
        return "ml"
