"""
Camada de persistência SQLite para o NotificAI.

Toda a informação sensível fica na tabela `patients`.
As demais tabelas usam apenas `patient_hash` como chave,
garantindo que o Painel Público nunca acesse identificadores reais.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

DB_PATH = Path(__file__).parent.parent / "data" / "notificai.db"

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS patients (
    patient_hash    TEXT PRIMARY KEY,
    rghc            TEXT,
    cpf             TEXT,
    nome_paciente   TEXT,
    codigo_paciente TEXT,
    data_nascimento TEXT,
    first_seen_at   TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id            TEXT PRIMARY KEY,
    patient_hash      TEXT REFERENCES patients(patient_hash),
    filename          TEXT NOT NULL,
    folder_path       TEXT,
    document_date     TEXT,
    document_type     TEXT,
    page_count        INTEGER DEFAULT 0,
    extraction_method TEXT,
    quality_level     TEXT,
    processed_at      TEXT NOT NULL,
    status            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id       TEXT PRIMARY KEY,
    doc_id            TEXT REFERENCES documents(doc_id),
    page_number       INTEGER,
    notification_type TEXT NOT NULL,
    confidence        REAL NOT NULL,
    score             REAL NOT NULL,
    severity_level    TEXT NOT NULL,
    mode              TEXT,
    processing_ms     REAL,
    analyzed_at       TEXT NOT NULL,
    all_probabilities TEXT
);

CREATE TABLE IF NOT EXISTS detections (
    detection_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id    TEXT REFERENCES analyses(analysis_id),
    term           TEXT NOT NULL,
    category       TEXT NOT NULL,
    weight         REAL NOT NULL,
    negated        INTEGER NOT NULL DEFAULT 0,
    context_phrase TEXT,
    sentence       TEXT,
    page_number    INTEGER,
    document_date  TEXT
);

CREATE TABLE IF NOT EXISTS access_log (
    log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_hash TEXT,
    action       TEXT NOT NULL,
    accessed_at  TEXT NOT NULL,
    session_id   TEXT
);

CREATE INDEX IF NOT EXISTS idx_analyses_type     ON analyses(notification_type);
CREATE INDEX IF NOT EXISTS idx_analyses_date     ON analyses(analyzed_at);
CREATE INDEX IF NOT EXISTS idx_analyses_severity ON analyses(severity_level);
CREATE INDEX IF NOT EXISTS idx_analyses_doc      ON analyses(doc_id);
CREATE INDEX IF NOT EXISTS idx_documents_patient ON documents(patient_hash);
CREATE INDEX IF NOT EXISTS idx_documents_date    ON documents(document_date);
CREATE INDEX IF NOT EXISTS idx_detections_ana    ON detections(analysis_id);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Abre (ou cria) o banco e retorna uma conexão thread-safe."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _apply_schema(conn)
    return conn


def _apply_schema(conn: sqlite3.Connection) -> None:
    with _lock:
        conn.executescript(_DDL)
        conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Context manager para transações com lock de escrita."""
    with _lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


# ---------------------------------------------------------------------------
# Queries de leitura (usadas pelos painéis)
# ---------------------------------------------------------------------------

def count_analyses(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()
    return int(row[0])


def count_by_type(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT notification_type, COUNT(*) AS total FROM analyses GROUP BY notification_type"
    ).fetchall()
    return [dict(r) for r in rows]


def count_by_severity(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT severity_level, COUNT(*) AS total FROM analyses GROUP BY severity_level"
    ).fetchall()
    return [dict(r) for r in rows]


def analyses_over_time(
    conn: sqlite3.Connection, freq: str = "week"
) -> List[Dict[str, Any]]:
    """Agrupa análises por semana ou mês para gráfico de série temporal."""
    if freq == "week":
        trunc = "strftime('%Y-W%W', analyzed_at)"
    else:
        trunc = "strftime('%Y-%m', analyzed_at)"
    rows = conn.execute(
        f"SELECT {trunc} AS period, COUNT(*) AS total, "
        f"AVG(score) AS avg_score FROM analyses GROUP BY period ORDER BY period"
    ).fetchall()
    return [dict(r) for r in rows]


def top_terms(
    conn: sqlite3.Connection, limit: int = 20
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT term, category, COUNT(*) AS freq, AVG(weight) AS avg_weight "
        "FROM detections WHERE negated=0 GROUP BY term "
        "ORDER BY freq DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def category_over_time(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT strftime('%Y-%m', d.analyzed_at) AS period, "
        "det.category, COUNT(*) AS total "
        "FROM detections det "
        "JOIN analyses d ON d.analysis_id = det.analysis_id "
        "WHERE det.negated=0 "
        "GROUP BY period, det.category ORDER BY period"
    ).fetchall()
    return [dict(r) for r in rows]


def priority_queue(
    conn: sqlite3.Connection, limit: int = 50
) -> List[Dict[str, Any]]:
    """Fila de casos priorizados por score decrescente (Painel Seguro)."""
    rows = conn.execute(
        """
        SELECT
            a.analysis_id, a.doc_id, a.notification_type,
            a.confidence, a.score, a.severity_level, a.analyzed_at,
            d.filename, d.patient_hash, d.document_date, d.page_count
        FROM analyses a
        JOIN documents d ON d.doc_id = a.doc_id
        WHERE a.page_number IS NULL
        ORDER BY a.score DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_analysis_detail(
    conn: sqlite3.Connection, analysis_id: str
) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT a.*, d.filename, d.patient_hash, d.document_date,
               d.folder_path, d.page_count, d.document_type
        FROM analyses a JOIN documents d ON d.doc_id = a.doc_id
        WHERE a.analysis_id = ?
        """,
        (analysis_id,),
    ).fetchone()
    return dict(row) if row else None


def get_detections(
    conn: sqlite3.Connection, analysis_id: str
) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM detections WHERE analysis_id = ? ORDER BY weight DESC",
        (analysis_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_patient(
    conn: sqlite3.Connection, patient_hash: str
) -> Optional[Dict[str, Any]]:
    """Apenas para o Painel Seguro após autenticação."""
    row = conn.execute(
        "SELECT * FROM patients WHERE patient_hash = ?", (patient_hash,)
    ).fetchone()
    return dict(row) if row else None


def log_access(
    conn: sqlite3.Connection,
    action: str,
    patient_hash: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    from datetime import datetime, timezone
    with transaction(conn):
        conn.execute(
            "INSERT INTO access_log(patient_hash, action, accessed_at, session_id) "
            "VALUES (?, ?, ?, ?)",
            (
                patient_hash,
                action,
                datetime.now(timezone.utc).isoformat(),
                session_id,
            ),
        )


def get_page_analyses(
    conn: sqlite3.Connection, doc_id: str
) -> List[Dict[str, Any]]:
    """Retorna análises por página de um documento (para mapa de detecções)."""
    rows = conn.execute(
        "SELECT page_number, notification_type, score, confidence "
        "FROM analyses WHERE doc_id = ? AND page_number IS NOT NULL "
        "ORDER BY page_number",
        (doc_id,),
    ).fetchall()
    return [dict(r) for r in rows]
