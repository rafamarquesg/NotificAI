"""
Testes do frontend NotificAI — componentes e lógica sem Streamlit.

Execute:
    cd frontend
    python -m pytest test_frontend.py -v

Não requer conexão com banco real (usa banco em memória).
"""

import sqlite3
import sys
from pathlib import Path
from datetime import date, datetime, timezone

import pytest

# Configurar path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_connection, _apply_schema
from core.export import _row_to_sinan, export_sinan_csv
from components.sinan_form import _build_csv, _build_summary_txt
from components.text_viewer import _apply_highlights, _escape_html


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mem_conn():
    """Banco SQLite em memória com schema aplicado."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _apply_schema(conn)
    return conn


def _insert_case(conn, ntype="Violência Física", score=15.0, severity="ALTO"):
    """Insere um documento + análise de teste no banco."""
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "doc-test-001"
    ana_id = "ana-test-001"
    patient_hash = "hash-test"

    conn.execute(
        """INSERT OR IGNORE INTO patients
           (patient_hash, first_seen_at, updated_at)
           VALUES (?, ?, ?)""",
        (patient_hash, now, now),
    )
    conn.execute(
        """INSERT OR IGNORE INTO documents
           (doc_id, patient_hash, filename, document_date,
            document_type, page_count, extraction_method,
            quality_level, processed_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (doc_id, patient_hash, "prontuario_teste.pdf", "2025-01-15",
         "Evolução Médica", 3, "direto", "GOOD", now, "sucesso"),
    )
    conn.execute(
        """INSERT OR IGNORE INTO analyses
           (analysis_id, doc_id, page_number, notification_type,
            confidence, score, severity_level, mode,
            processing_ms, analyzed_at, case_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ana_id, doc_id, None, ntype,
         0.78, score, severity, "rules",
         12.5, now, "pendente"),
    )
    conn.execute(
        """INSERT INTO detections
           (analysis_id, term, category, weight, negated,
            context_phrase, sentence)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ana_id, "agressão", "medical_formal", 3.0, 0,
         "Paciente relata agressão pelo companheiro",
         "Paciente relata agressão pelo companheiro com socos."),
    )
    conn.execute(
        """INSERT INTO detections
           (analysis_id, term, category, weight, negated,
            context_phrase, sentence)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ana_id, "violência", "legal_police", 2.5, 0,
         "Boletim de ocorrência de violência doméstica",
         "Boletim de ocorrência de violência doméstica registrado."),
    )
    conn.commit()
    return ana_id, doc_id, patient_hash


# ---------------------------------------------------------------------------
# Testes — banco de dados
# ---------------------------------------------------------------------------

class TestDatabase:
    def test_schema_creates_tables(self, mem_conn):
        tables = {
            row[0] for row in
            mem_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "patients" in tables
        assert "documents" in tables
        assert "analyses" in tables
        assert "detections" in tables
        assert "feedback" in tables
        assert "access_log" in tables

    def test_insert_and_retrieve_case(self, mem_conn):
        ana_id, doc_id, patient_hash = _insert_case(mem_conn)

        row = mem_conn.execute(
            "SELECT * FROM analyses WHERE analysis_id = ?", (ana_id,)
        ).fetchone()
        assert row is not None
        assert row["notification_type"] == "Violência Física"
        assert row["score"] == 15.0
        assert row["severity_level"] == "ALTO"
        assert row["case_status"] == "pendente"

    def test_update_case_status(self, mem_conn):
        from core.database import update_case_status
        ana_id, _, _ = _insert_case(mem_conn)

        update_case_status(mem_conn, ana_id, "notificado", assigned_to="Ana Silva")

        row = mem_conn.execute(
            "SELECT case_status, assigned_to FROM analyses WHERE analysis_id = ?",
            (ana_id,),
        ).fetchone()
        assert row["case_status"] == "notificado"
        assert row["assigned_to"] == "Ana Silva"

    def test_add_feedback(self, mem_conn):
        from core.database import add_feedback, get_feedback_stats
        ana_id, _, _ = _insert_case(mem_conn)

        add_feedback(
            mem_conn, ana_id,
            original_type="Violência Física",
            corrected_type="Violência Física",
            correct=True,
            session_id="session-x",
        )
        stats = get_feedback_stats(mem_conn)
        assert stats["total"] == 1
        assert stats["correct"] == 1
        assert stats["accuracy"] == 1.0

    def test_feedback_incorrect(self, mem_conn):
        from core.database import add_feedback, get_feedback_stats
        ana_id, _, _ = _insert_case(mem_conn)

        add_feedback(
            mem_conn, ana_id,
            original_type="Violência Física",
            corrected_type="Violência Sexual",
            correct=False,
            session_id="session-y",
        )
        stats = get_feedback_stats(mem_conn)
        assert stats["accuracy"] == 0.0
        assert len(stats["corrections"]) == 1

    def test_priority_queue(self, mem_conn):
        from core.database import priority_queue_filtered
        _insert_case(mem_conn, score=20.0, severity="CRÍTICO")

        cases = priority_queue_filtered(mem_conn, limit=10)
        assert len(cases) >= 1
        assert cases[0]["score"] == 20.0

    def test_patient_timeline(self, mem_conn):
        from core.database import get_patient_timeline
        _, _, patient_hash = _insert_case(mem_conn)

        timeline = get_patient_timeline(mem_conn, patient_hash)
        assert len(timeline) >= 1
        assert timeline[0]["notification_type"] == "Violência Física"

    def test_get_cases_for_export(self, mem_conn):
        from core.database import get_cases_for_export
        _insert_case(mem_conn)

        rows = get_cases_for_export(mem_conn)
        assert len(rows) >= 1
        # Nunca deve expor PII direta — sem nome, só hash
        assert "nome_paciente" not in rows[0]
        assert "patient_hash" in rows[0]


# ---------------------------------------------------------------------------
# Testes — exportação SINAN
# ---------------------------------------------------------------------------

class TestExport:
    def test_row_to_sinan_mapping(self):
        row = {
            "notification_type": "Violência Sexual",
            "analyzed_at":       "2025-03-15T10:00:00+00:00",
            "document_date":     "2025-03-10",
            "severity_level":    "CRÍTICO",
            "score":             25.0,
            "confidence":        0.91,
            "case_status":       "notificado",
            "patient_hash":      "abcdef1234567890",
            "page_count":        4,
            "analysis_id":       "ana-xyz-001",
        }
        mapped = _row_to_sinan(row)
        assert mapped["TIPO_VIOL"] == "2"       # violência sexual
        assert mapped["ID_AGRAVO"] == "T74.2"
        assert mapped["TP_NOT"]    == "4"
        assert mapped["DT_NOTIF"]  == "15/03/2025"
        assert mapped["DT_OCOR"]   == "10/03/2025"
        assert "abcdef12" in mapped["HASH_PACIENTE"]

    def test_export_csv_returns_bytes(self, mem_conn):
        _insert_case(mem_conn)
        csv_bytes = export_sinan_csv(mem_conn)
        assert isinstance(csv_bytes, bytes)
        assert len(csv_bytes) > 0
        # Deve ter BOM UTF-8
        assert csv_bytes[:3] == b"\xef\xbb\xbf"
        # Deve ter cabeçalho
        text = csv_bytes.decode("utf-8-sig")
        assert "DT_NOTIF" in text
        assert "TIPO_VIOL" in text

    def test_sinan_form_build_csv(self):
        csv_bytes = _build_csv(
            analysis_id="test-123",
            ntype="Violência Física",
            dt_notif=date(2025, 3, 15),
            dt_ocor=date(2025, 3, 10),
            dt_nasc=date(1990, 5, 20),
            sexo="Feminino",
            raca="Parda",
            escolaridade="Ensino médio completo",
            uf="SP",
            municipio="São Paulo",
            local="Residência",
            vinculo="Cônjuge/companheiro",
            evolucao="Alta",
            patient_hash="hash-paciente-xyz",
            observacoes="Teste de geração de CSV",
        )
        assert isinstance(csv_bytes, bytes)
        text = csv_bytes.decode("utf-8-sig")
        assert "TIPO_VIOL" in text
        assert "1" in text  # código violência física

    def test_sinan_form_build_txt(self):
        txt = _build_summary_txt(
            analysis_id="test-456",
            ntype="Negligência/Abandono",
            dt_notif=date(2025, 3, 15),
            dt_ocor=date(2025, 3, 10),
            rghc="12345678",
            sexo="Feminino",
            raca="Parda",
            local="Residência",
            vinculo="Cônjuge/companheiro",
            evolucao="Encaminhamento",
            score=8.5,
            confidence=0.72,
            severity="MODERADO",
            obs="Criança em situação de risco",
            tech_nome="João Santos",
        )
        assert "Negligência/Abandono" in txt
        assert "T74.0" in txt
        assert "João Santos" in txt
        assert "NUVE HC-FMUSP" in txt


# ---------------------------------------------------------------------------
# Testes — visualizador de texto
# ---------------------------------------------------------------------------

class TestTextViewer:
    def test_escape_html(self):
        assert _escape_html("<b>test</b>") == "&lt;b&gt;test&lt;/b&gt;"
        assert _escape_html("a & b")       == "a &amp; b"

    def test_apply_highlights_no_detections(self):
        text = "Texto simples sem detecções."
        result = _apply_highlights(text, [])
        assert "mark" not in result
        assert "Texto simples" in result

    def test_apply_highlights_with_match(self):
        text = "Paciente relata agressão pelo parceiro."
        detections = [
            {
                "position_start": 17,
                "position_end":   24,
                "category":       "medical_formal",
                "term":           "agressão",
                "negated":        False,
            }
        ]
        result = _apply_highlights(text, detections)
        assert "<mark" in result
        assert "agressão" in result
        assert "background" in result

    def test_apply_highlights_negated(self):
        text = "Nega agressão pelo parceiro."
        detections = [
            {
                "position_start": 5,
                "position_end":   13,
                "category":       "medical_formal",
                "term":           "agressão",
                "negated":        True,
            }
        ]
        result = _apply_highlights(text, detections)
        assert "line-through" in result

    def test_apply_highlights_no_overlap(self):
        text = "violência doméstica e agressão física."
        detections = [
            {"position_start": 0, "position_end": 9, "category": "legal_police",
             "term": "violência", "negated": False},
            {"position_start": 22, "position_end": 30, "category": "medical_formal",
             "term": "agressão", "negated": False},
        ]
        result = _apply_highlights(text, detections)
        assert result.count("<mark") == 2


# ---------------------------------------------------------------------------
# Testes — worklist (lógica de filtro)
# ---------------------------------------------------------------------------

class TestWorklist:
    def test_priority_filter_by_status(self, mem_conn):
        from core.database import update_case_status, priority_queue_filtered
        ana_id, _, _ = _insert_case(mem_conn)
        update_case_status(mem_conn, ana_id, "notificado")

        pending = priority_queue_filtered(mem_conn, status_filter="pendente")
        assert all(c["case_status"] == "pendente" for c in pending)

        notified = priority_queue_filtered(mem_conn, status_filter="notificado")
        assert any(c["analysis_id"] == ana_id for c in notified)

    def test_priority_order_by_score(self, mem_conn):
        from core.database import priority_queue_filtered

        now = datetime.now(timezone.utc).isoformat()
        for i, score in enumerate([5.0, 25.0, 15.0]):
            doc_id = f"doc-ord-{i}"
            ana_id = f"ana-ord-{i}"
            patient_hash = f"hash-ord-{i}"
            mem_conn.execute(
                "INSERT OR IGNORE INTO patients (patient_hash, first_seen_at, updated_at) VALUES (?,?,?)",
                (patient_hash, now, now),
            )
            mem_conn.execute(
                """INSERT OR IGNORE INTO documents
                   (doc_id, patient_hash, filename, processed_at, status)
                   VALUES (?,?,?,?,?)""",
                (doc_id, patient_hash, f"doc{i}.pdf", now, "sucesso"),
            )
            mem_conn.execute(
                """INSERT OR IGNORE INTO analyses
                   (analysis_id, doc_id, notification_type, confidence,
                    score, severity_level, mode, analyzed_at, case_status)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (ana_id, doc_id, "Violência Física", 0.7, score,
                 "ALTO", "rules", now, "pendente"),
            )
        mem_conn.commit()

        cases = priority_queue_filtered(mem_conn, limit=10)
        scores = [c["score"] for c in cases]
        assert scores == sorted(scores, reverse=True)
