"""Pipeline integrado de triagem lexical.

Orquestra as sete etapas descritas na metodologia:
  1. Extração de Texto              (EnhancedTextExtractor)
  2. Classificação de Documentos    (DocumentClassifier)
  3. Identificação de Pacientes     (EnhancedPatientIdentifier)
  4. Análise Lexical                (EnhancedViolenceAnalyzer)
  5. Análise Contextual             (densidade terminológica)
  6. Sistema de Pontuação           (score + bônus)
  7. Classificação de Severidade    (CRITICO/ALTO/.../MINIMO)
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from analyzer import AnalysisResult, EnhancedViolenceAnalyzer
from classifier import DocumentClassifier, DocumentMeta
from extractor import EnhancedTextExtractor, ExtractionResult
from identifier import EnhancedPatientIdentifier, PatientId
from scoring import SeverityClassification, classify_severity


@dataclass
class CaseReport:
    source: str
    extraction: ExtractionResult
    document: DocumentMeta
    patient: PatientId
    analysis: AnalysisResult
    severity: SeverityClassification
    elapsed_seconds: float


class TriagePipeline:
    def __init__(self):
        self.extractor = EnhancedTextExtractor()
        self.classifier = DocumentClassifier()
        self.identifier = EnhancedPatientIdentifier()
        self.analyzer = EnhancedViolenceAnalyzer()

    def process(self, pdf_path: str | Path) -> CaseReport:
        t0 = time.perf_counter()
        ext = self.extractor.extract(pdf_path)
        text = ext.text
        doc_meta = self.classifier.classify(text)
        patient = self.identifier.extract(text, source_filename=str(pdf_path))
        analysis = self.analyzer.analyze(text)
        has_crit = bool(analysis.contextual.critical_pattern_hits)
        severity = classify_severity(analysis.final_score, has_critical_pattern=has_crit)
        elapsed = time.perf_counter() - t0
        return CaseReport(
            source=str(pdf_path),
            extraction=ext,
            document=doc_meta,
            patient=patient,
            analysis=analysis,
            severity=severity,
            elapsed_seconds=round(elapsed, 3),
        )


def case_summary_row(report: CaseReport) -> dict:
    a = report.analysis
    return {
        "fonte": report.source,
        "metodo_extracao": report.extraction.method,
        "paginas": report.extraction.pages,
        "qualidade_extracao": report.extraction.quality_score,
        "tipo_documento": report.document.doc_type,
        "matricula": report.patient.matricula,
        "anon_hash": report.patient.anon_hash,
        "n_deteccoes": len(a.detections),
        "n_deteccoes_negadas": sum(1 for d in a.detections if d.negated),
        "categorias_unicas": len({d.category for d in a.detections if not d.negated}),
        "densidade_traumatica": a.contextual.medical_trauma_density,
        "evasao_marcadores": a.contextual.evasion_count,
        "padroes_criticos": ";".join(a.contextual.critical_pattern_hits.keys()),
        "score_base": a.base_score,
        "bonus_contextual": a.contextual_bonus,
        "score_final": a.final_score,
        "severidade": report.severity.label,
        "limiar_ajustado": report.severity.adjusted_thresholds,
        "tempo_segundos": report.elapsed_seconds,
    }


def detection_rows(report: CaseReport) -> list[dict]:
    rows = []
    for d in report.analysis.detections:
        rows.append({
            "matricula": report.patient.matricula,
            "anon_hash": report.patient.anon_hash,
            "termo": d.term,
            "categoria": d.category,
            "peso": d.weight,
            "posicao": d.position,
            "negado": d.negated,
            "fator_intensidade": d.intensity_factor,
            "contribuicao": d.contribution,
            "contexto": d.context,
        })
    return rows
