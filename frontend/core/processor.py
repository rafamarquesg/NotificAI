"""
Orquestrador de processamento de documentos.

Integra extração de texto (EnhancedTextExtractor), pipeline de análise
(AnalysisPipeline), anonimização e persistência em uma transação atômica.
"""

import sys
import uuid
import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Resolver módulos do backend
_BACKEND = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_BACKEND))

from pipeline import AnalysisPipeline
from core.database import transaction
from core.anonymizer import extract_identifiers, upsert_patient

# Importar extrator de texto do complete.py (se disponível)
try:
    from complete import (
        EnhancedTextExtractor,
        ProcessingConfig,
        ProcessingStatus,
    )
    HAS_EXTRACTOR = True
except Exception:
    HAS_EXTRACTOR = False

# Pipeline global (inicializado uma vez)
_pipeline: Optional[AnalysisPipeline] = None


def get_pipeline() -> AnalysisPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = AnalysisPipeline()
    return _pipeline


# ---------------------------------------------------------------------------
# Mapeamento de score → severidade
# ---------------------------------------------------------------------------

def _severity(score: float) -> str:
    if score >= 20:
        return "CRÍTICO"
    if score >= 12:
        return "ALTO"
    if score >= 6:
        return "MODERADO"
    if score >= 2:
        return "BAIXO"
    if score > 0:
        return "MÍNIMO"
    return "SEM INDICAÇÃO"


# ---------------------------------------------------------------------------
# Resultado do processamento
# ---------------------------------------------------------------------------

@dataclass
class ProcessingResult:
    doc_id: str
    patient_hash: str
    filename: str
    notification_type: str
    severity_level: str
    confidence: float
    score: float
    page_count: int
    status: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def process_file(
    conn,
    file_bytes: bytes,
    filename: str,
    folder_path: Optional[str] = None,
) -> ProcessingResult:
    """
    Processa um PDF ou texto e persiste os resultados no banco.

    1. Deduplica por hash do conteúdo do arquivo.
    2. Extrai texto (via EnhancedTextExtractor ou leitura direta).
    3. Extrai e anonimiza identificadores do paciente.
    4. Analisa cada página + documento completo com o pipeline.
    5. Persiste `documents`, `analyses` e `detections`.

    Retorna ProcessingResult com os dados principais.
    """
    from hashlib import sha256
    doc_id = sha256(file_bytes).hexdigest()
    now = datetime.now(timezone.utc).isoformat()

    # Deduplicação
    existing = conn.execute(
        "SELECT doc_id, patient_hash, status FROM documents WHERE doc_id = ?",
        (doc_id,),
    ).fetchone()
    if existing:
        # Retornar resultado do processamento anterior
        ana = conn.execute(
            "SELECT notification_type, confidence, score, severity_level "
            "FROM analyses WHERE doc_id = ? AND page_number IS NULL LIMIT 1",
            (doc_id,),
        ).fetchone()
        return ProcessingResult(
            doc_id=doc_id,
            patient_hash=existing["patient_hash"] or "",
            filename=existing["filename"] if hasattr(existing, "__getitem__") else filename,
            notification_type=ana["notification_type"] if ana else "Outros/Não Classificado",
            severity_level=ana["severity_level"] if ana else "SEM INDICAÇÃO",
            confidence=float(ana["confidence"]) if ana else 0.0,
            score=float(ana["score"]) if ana else 0.0,
            page_count=0,
            status="duplicado",
        )

    # --- Extração de texto ---
    full_text = ""
    pages: List[dict] = []
    doc_date = None
    doc_type = "Outros"
    quality = "regular"
    extraction_method = "direto"
    page_count = 1
    status = "sucesso"
    error_msg = None

    is_pdf = filename.lower().endswith(".pdf")

    if is_pdf and HAS_EXTRACTOR:
        try:
            config = ProcessingConfig()
            extractor = EnhancedTextExtractor(config)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = Path(tmp.name)
            text_content = extractor.extract_from_pdf(tmp_path)
            tmp_path.unlink(missing_ok=True)

            full_text = text_content.text
            page_count = text_content.page_count
            extraction_method = text_content.extraction_method
            quality = text_content.quality_level.value if hasattr(text_content.quality_level, "value") else str(text_content.quality_level)
            doc_date = getattr(text_content.document_metadata, "document_date", None)
            doc_type = getattr(text_content.document_metadata, "document_type", "Outros")
            if hasattr(doc_type, "value"):
                doc_type = doc_type.value
            pages = [
                {"page_number": p.page_number, "text": p.page_text}
                for p in (text_content.pages_info or [])
            ]
        except Exception as exc:
            status = "erro_extracao"
            error_msg = str(exc)
            full_text = ""
    elif not is_pdf:
        # Texto puro
        try:
            full_text = file_bytes.decode("utf-8", errors="replace")
            extraction_method = "texto_puro"
        except Exception as exc:
            status = "erro_extracao"
            error_msg = str(exc)

    # --- Identificadores e anonimização ---
    ids = extract_identifiers(full_text)
    patient_hash = upsert_patient(conn, ids)

    # --- Persistir documento ---
    with transaction(conn):
        conn.execute(
            """INSERT INTO documents
               (doc_id, patient_hash, filename, folder_path, document_date,
                document_type, page_count, extraction_method, quality_level,
                processed_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc_id, patient_hash, filename, folder_path, doc_date,
                doc_type, page_count, extraction_method, quality, now, status,
            ),
        )

    if not full_text.strip():
        return ProcessingResult(
            doc_id=doc_id, patient_hash=patient_hash, filename=filename,
            notification_type="Outros/Não Classificado", severity_level="SEM INDICAÇÃO",
            confidence=0.0, score=0.0, page_count=page_count,
            status=status, error=error_msg or "texto_insuficiente",
        )

    # --- Análise: documento completo ---
    pipeline = get_pipeline()
    result = pipeline.analyze_text(full_text)
    analysis_id = str(uuid.uuid4())
    severity = _severity(result["score"])
    all_proba = {k.value: v for k, v in result["all_probabilities"].items()}

    _persist_analysis(
        conn, analysis_id, doc_id, None, result, severity, all_proba, now
    )

    # --- Análise: por página ---
    for page in pages:
        if not page["text"].strip():
            continue
        page_result = pipeline.analyze_text(page["text"])
        page_analysis_id = str(uuid.uuid4())
        page_severity = _severity(page_result["score"])
        page_proba = {k.value: v for k, v in page_result["all_probabilities"].items()}
        _persist_analysis(
            conn, page_analysis_id, doc_id, page["page_number"],
            page_result, page_severity, page_proba, now
        )

    return ProcessingResult(
        doc_id=doc_id,
        patient_hash=patient_hash,
        filename=filename,
        notification_type=result["notification_type"].value,
        severity_level=severity,
        confidence=result["confidence"],
        score=result["score"],
        page_count=page_count,
        status=status,
        error=error_msg,
    )


def _persist_analysis(
    conn, analysis_id, doc_id, page_number, result, severity, all_proba, now
):
    with transaction(conn):
        conn.execute(
            """INSERT INTO analyses
               (analysis_id, doc_id, page_number, notification_type, confidence,
                score, severity_level, mode, processing_ms, analyzed_at, all_probabilities)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                analysis_id, doc_id, page_number,
                result["notification_type"].value,
                result["confidence"], result["score"], severity,
                result.get("mode", "rules"),
                result.get("processing_ms"), now,
                json.dumps(all_proba),
            ),
        )
        for det in result.get("detections", []):
            conn.execute(
                """INSERT INTO detections
                   (analysis_id, term, category, weight, negated,
                    context_phrase, sentence, page_number, document_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    analysis_id,
                    det.get("term"), det.get("category"),
                    det.get("weight", 0.0),
                    1 if det.get("negated") else 0,
                    det.get("context", "")[:300],
                    det.get("sentence", "")[:500],
                    page_number, None,
                ),
            )
