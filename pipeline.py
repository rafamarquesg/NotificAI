"""Orquestração das 7 etapas do pipeline descrito na metodologia."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from analyzer import AnalysisResult, EnhancedViolenceAnalyzer
from config import ProcessingConfig, ProcessingStatus
from extractor import EnhancedTextExtractor, ExtractionResult
from identifier import EnhancedPatientIdentifier, PatientIdentifier
from metadata import DocumentMetadata, DocumentMetadataExtractor
from scoring import SeverityClassification, classify_severity


@dataclass
class CaseReport:
    source: str
    status: ProcessingStatus
    extraction: Optional[ExtractionResult]
    metadata: Optional[DocumentMetadata]
    patient: Optional[PatientIdentifier]
    analysis: Optional[AnalysisResult]
    severity: Optional[SeverityClassification]
    elapsed_ms: int
    error_message: Optional[str] = None


class TriagePipeline:
    def __init__(self, config: ProcessingConfig | None = None):
        self.config = config or ProcessingConfig()
        self.extractor = EnhancedTextExtractor(self.config)
        self.metadata_extractor = DocumentMetadataExtractor()
        self.identifier = EnhancedPatientIdentifier(self.config)
        self.analyzer = EnhancedViolenceAnalyzer(self.config)

    def process(self, pdf_path: str | Path) -> CaseReport:
        t0 = time.perf_counter()
        path = Path(pdf_path)
        try:
            extraction = self.extractor.extract(path)
            meta = self.metadata_extractor.extract(extraction.text, extraction.pages)
            patient = self.identifier.extract(extraction.text, source_filename=str(path))
            analysis = self.analyzer.analyze(extraction, document_date=meta.document_date)
            severity = classify_severity(analysis.total_score, analysis.patterns)
            return CaseReport(
                source=str(path), status=ProcessingStatus.SUCCESS,
                extraction=extraction, metadata=meta, patient=patient,
                analysis=analysis, severity=severity,
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
            )
        except Exception as exc:
            return CaseReport(
                source=str(path), status=ProcessingStatus.PROCESSING_ERROR,
                extraction=None, metadata=None, patient=None,
                analysis=None, severity=None,
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
                error_message=str(exc),
            )
