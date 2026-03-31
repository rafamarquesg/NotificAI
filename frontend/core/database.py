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
    all_probabilities TEXT,
    -- Workflow de acompanhamento do caso
    case_status       TEXT NOT NULL DEFAULT 'pendente',
    assigned_to       TEXT,
    status_updated_at TEXT,
    notes             TEXT
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

-- Feedback para aprendizado ativo (corrige classificação automática)
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id       TEXT REFERENCES analyses(analysis_id),
    original_type     TEXT NOT NULL,
    corrected_type    TEXT NOT NULL,
    correct           INTEGER NOT NULL DEFAULT 0,
    session_id        TEXT,
    submitted_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyses_type     ON analyses(notification_type);
CREATE INDEX IF NOT EXISTS idx_analyses_date     ON analyses(analyzed_at);
CREATE INDEX IF NOT EXISTS idx_analyses_severity ON analyses(severity_level);
CREATE INDEX IF NOT EXISTS idx_analyses_doc      ON analyses(doc_id);
CREATE INDEX IF NOT EXISTS idx_analyses_status   ON analyses(case_status);
CREATE INDEX IF NOT EXISTS idx_documents_patient ON documents(patient_hash);
CREATE INDEX IF NOT EXISTS idx_documents_date    ON documents(document_date);
CREATE INDEX IF NOT EXISTS idx_detections_ana    ON detections(analysis_id);
CREATE INDEX IF NOT EXISTS idx_feedback_ana      ON feedback(analysis_id);
"""

# Migrações incrementais para bancos existentes (idempotente)
_MIGRATIONS = [
    "ALTER TABLE analyses ADD COLUMN case_status TEXT NOT NULL DEFAULT 'pendente'",
    "ALTER TABLE analyses ADD COLUMN assigned_to TEXT",
    "ALTER TABLE analyses ADD COLUMN status_updated_at TEXT",
    "ALTER TABLE analyses ADD COLUMN notes TEXT",
]


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
        # Migrações incrementais: ignora erros de coluna já existente
        for sql in _MIGRATIONS:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass
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


# ---------------------------------------------------------------------------
# Workflow de status de caso
# ---------------------------------------------------------------------------

CASE_STATUSES = ["pendente", "em análise", "notificado", "arquivado"]


def update_case_status(
    conn: sqlite3.Connection,
    analysis_id: str,
    new_status: str,
    assigned_to: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Atualiza o status de workflow de um caso."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    with transaction(conn):
        conn.execute(
            """
            UPDATE analyses
            SET case_status = ?,
                assigned_to = COALESCE(?, assigned_to),
                notes = COALESCE(?, notes),
                status_updated_at = ?
            WHERE analysis_id = ?
            """,
            (new_status, assigned_to, notes, now, analysis_id),
        )


def count_by_status(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Contagem de análises por status de caso (nível documento)."""
    rows = conn.execute(
        """
        SELECT case_status, COUNT(*) AS total
        FROM analyses
        WHERE page_number IS NULL
        GROUP BY case_status
        """
    ).fetchall()
    return [dict(r) for r in rows]


def priority_queue_filtered(
    conn: sqlite3.Connection,
    limit: int = 50,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fila de prioridade com filtros opcionais."""
    clauses = ["a.page_number IS NULL"]
    params: list = []
    if status_filter:
        clauses.append("a.case_status = ?")
        params.append(status_filter)
    if type_filter:
        clauses.append("a.notification_type = ?")
        params.append(type_filter)
    if severity_filter:
        clauses.append("a.severity_level = ?")
        params.append(severity_filter)
    where = " AND ".join(clauses)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT
            a.analysis_id, a.doc_id, a.notification_type,
            a.confidence, a.score, a.severity_level, a.analyzed_at,
            a.case_status, a.assigned_to, a.notes,
            d.filename, d.patient_hash, d.document_date, d.page_count
        FROM analyses a
        JOIN documents d ON d.doc_id = a.doc_id
        WHERE {where}
        ORDER BY a.score DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Timeline do paciente (reincidência)
# ---------------------------------------------------------------------------

def get_patient_timeline(
    conn: sqlite3.Connection, patient_hash: str
) -> List[Dict[str, Any]]:
    """Todos os documentos e análises associados a um paciente (hash)."""
    rows = conn.execute(
        """
        SELECT
            a.analysis_id, a.notification_type, a.score, a.severity_level,
            a.confidence, a.case_status, a.analyzed_at,
            d.filename, d.document_date, d.page_count, d.doc_id
        FROM analyses a
        JOIN documents d ON d.doc_id = a.doc_id
        WHERE d.patient_hash = ? AND a.page_number IS NULL
        ORDER BY d.document_date ASC, a.analyzed_at ASC
        """,
        (patient_hash,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Comparação de períodos (para gestores)
# ---------------------------------------------------------------------------

def count_period_comparison(
    conn: sqlite3.Connection, freq: str = "month"
) -> Dict[str, Any]:
    """
    Compara o período atual com o anterior.
    Retorna: {current, previous, delta_abs, delta_pct}
    """
    if freq == "week":
        period_sql = "strftime('%Y-W%W', analyzed_at)"
        current_period = __import__("datetime").date.today().strftime("%Y-W%W")
    else:
        period_sql = "strftime('%Y-%m', analyzed_at)"
        current_period = __import__("datetime").date.today().strftime("%Y-%m")

    rows = conn.execute(
        f"SELECT {period_sql} AS period, COUNT(*) AS total "
        f"FROM analyses WHERE page_number IS NULL "
        f"GROUP BY period ORDER BY period DESC LIMIT 2"
    ).fetchall()
    rows = [dict(r) for r in rows]

    current  = rows[0]["total"] if rows else 0
    previous = rows[1]["total"] if len(rows) > 1 else 0
    delta_abs = current - previous
    delta_pct = (delta_abs / previous * 100) if previous > 0 else None
    return {
        "current":   current,
        "previous":  previous,
        "delta_abs": delta_abs,
        "delta_pct": delta_pct,
    }


# ---------------------------------------------------------------------------
# Exportação (SINAN / CSV)
# ---------------------------------------------------------------------------

def get_cases_for_export(
    conn: sqlite3.Connection,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    notification_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retorna dados para exportação CSV/SINAN (sem PII)."""
    clauses = ["a.page_number IS NULL"]
    params: list = []
    if start_date:
        clauses.append("a.analyzed_at >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("a.analyzed_at <= ?")
        params.append(end_date + "T23:59:59")
    if notification_type:
        clauses.append("a.notification_type = ?")
        params.append(notification_type)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT
            a.analysis_id,
            a.notification_type,
            a.severity_level,
            a.score,
            a.confidence,
            a.case_status,
            a.analyzed_at,
            d.document_date,
            d.document_type,
            d.page_count,
            d.patient_hash
        FROM analyses a
        JOIN documents d ON d.doc_id = a.doc_id
        WHERE {where}
        ORDER BY a.analyzed_at DESC
        """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Feedback / aprendizado ativo
# ---------------------------------------------------------------------------

def add_feedback(
    conn: sqlite3.Connection,
    analysis_id: str,
    original_type: str,
    corrected_type: str,
    correct: bool,
    session_id: Optional[str] = None,
) -> None:
    """Registra feedback de classificação para aprendizado ativo."""
    from datetime import datetime, timezone
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO feedback
                (analysis_id, original_type, corrected_type, correct, session_id, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                original_type,
                corrected_type,
                int(correct),
                session_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_feedback_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Estatísticas de acurácia com base no feedback coletado."""
    row = conn.execute(
        "SELECT COUNT(*) AS total, SUM(correct) AS correct_count FROM feedback"
    ).fetchone()
    total   = row["total"] or 0
    correct = row["correct_count"] or 0
    accuracy = correct / total if total > 0 else None
    corrections = conn.execute(
        """
        SELECT original_type, corrected_type, COUNT(*) AS freq
        FROM feedback WHERE correct=0
        GROUP BY original_type, corrected_type
        ORDER BY freq DESC LIMIT 10
        """
    ).fetchall()
    return {
        "total":       total,
        "correct":     correct,
        "accuracy":    accuracy,
        "corrections": [dict(r) for r in corrections],
    }
