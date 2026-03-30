"""
Pipeline de análise completo: texto → detecção → características → classificação.

Integra todos os módulos do sistema NUVE em uma única interface de entrada.
Quando um caminho de modelo for fornecido e o arquivo existir, usa ML;
caso contrário, opera via regras lexicais sem configuração adicional.
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

    Etapas executadas por `analyze_text`:
      1. Detecção lexical de termos de violência  (ViolenceDetector)
      2. Extração de características NLP          (FeatureExtractor)
      3. Classificação do tipo de notificação     (NotificationClassifier)

    Uso básico (sem modelo treinado — modo regras):
        pipeline = AnalysisPipeline()
        result = pipeline.analyze_text("Paciente vítima de violência doméstica.")
        print(result["notification_type"].value, result["confidence"])

    Uso com modelo treinado:
        pipeline = AnalysisPipeline(model_path="modelo_nuve.pkl")
        result = pipeline.analyze_text(texto)

    Treinamento e persistência (quando dados rotulados estiverem disponíveis):
        pipeline = AnalysisPipeline()
        pipeline.classifier.fit(texts, labels)
        pipeline.classifier.save("modelo_nuve.pkl")
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        """
        Args:
            model_path: caminho opcional para um modelo .pkl salvo por
                        NotificationClassifier.save(). Se o arquivo não
                        existir, o pipeline opera no modo regras.
        """
        self._detector = ViolenceDetector()
        self._extractor = FeatureExtractor()

        if model_path and Path(model_path).exists():
            logger.info("Carregando modelo ML de: %s", model_path)
            self._classifier = NotificationClassifier.load(model_path)
        else:
            if model_path:
                logger.warning(
                    "Modelo não encontrado em '%s'. Usando modo regras.", model_path
                )
            self._classifier = NotificationClassifier()

    # ------------------------------------------------------------------
    # Análise
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analisa um texto e retorna um dicionário com todos os resultados.

        Retorno:
            {
              "detections":        List[dict]        — termos detectados,
              "score":             float             — pontuação total (sem negados),
              "features":          dict              — características interpretáveis,
              "notification_type": NotificationType  — tipo de notificação inferido,
              "confidence":        float [0, 1]      — confiança da classificação,
              "all_probabilities": Dict[NotificationType, float],
              "mode":              "ml" | "rules"    — modo de classificação usado,
              "processing_ms":     float             — tempo de processamento,
            }
        """
        start = time.perf_counter()

        detections = self._detector.analyze(text)
        score = sum(d["weight"] for d in detections if not d["negated"])
        features = self._extractor.extract(text)
        ntype, confidence = self._classifier.predict(text)
        all_proba = self._classifier.predict_proba(text)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "detections": detections,
            "score": round(score, 3),
            "features": features,
            "notification_type": ntype,
            "confidence": confidence,
            "all_probabilities": all_proba,
            "mode": "ml" if self._classifier.is_trained else "rules",
            "processing_ms": elapsed_ms,
        }

    def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Analisa uma lista de textos e retorna uma lista de resultados.

        Útil para processamento em lote de prontuários.
        """
        return [self.analyze_text(t) for t in texts]

    def summary(self, result: Dict[str, Any]) -> str:
        """
        Gera um resumo legível de um resultado de análise.

        Args:
            result: dicionário retornado por `analyze_text`.

        Returns:
            String formatada com os principais achados.
        """
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
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Acesso aos componentes internos
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
