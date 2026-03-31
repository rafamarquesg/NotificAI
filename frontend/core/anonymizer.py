"""
Anonimização de dados do paciente com associação controlada.

O `patient_hash` é o pseudônimo estável derivado dos identificadores.
Somente o Painel Seguro (autenticado) pode resolver hash → identificadores reais.
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils import hash_text
from core.database import transaction

# ---------------------------------------------------------------------------
# Extração de identificadores do texto
# ---------------------------------------------------------------------------

_RGHC_RE  = re.compile(r'\b(?:RGHC?|RG\s*HC)\s*[:\-]?\s*(\d{5,12})\b', re.IGNORECASE)
_CPF_RE   = re.compile(r'\b(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})\b')
_DOB_RE   = re.compile(r'\b(?:DN|nascimento|nasc\.?)\s*[:\-]?\s*(\d{2}[/\-]\d{2}[/\-]\d{4})\b', re.IGNORECASE)
_NAME_RE  = re.compile(
    r'\b(?:paciente|nome|pac\.?)\s*[:\-]?\s*'
    r'([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇ][a-záéíóúâêîôûãõàèìòùç]+'
    r'(?:\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÇ][a-záéíóúâêîôûãõàèìòùç]+){1,5})',
    re.UNICODE,
)


def extract_identifiers(text: str) -> Dict[str, Optional[str]]:
    """
    Extrai identificadores do paciente a partir do texto do documento.

    Retorna dicionário com chaves:
        rghc, cpf, nome_paciente, data_nascimento
    Valores ausentes são None.
    """
    rghc_m  = _RGHC_RE.search(text)
    cpf_m   = _CPF_RE.search(text)
    dob_m   = _DOB_RE.search(text)
    name_m  = _NAME_RE.search(text)

    # Normalizar CPF: remover pontuação
    cpf = re.sub(r'[\.\s\-]', '', cpf_m.group(1)) if cpf_m else None

    return {
        "rghc":            rghc_m.group(1) if rghc_m else None,
        "cpf":             cpf,
        "nome_paciente":   name_m.group(1).strip() if name_m else None,
        "data_nascimento": dob_m.group(1) if dob_m else None,
    }


# ---------------------------------------------------------------------------
# Cálculo e persistência do hash
# ---------------------------------------------------------------------------

def compute_hash(ids: Dict[str, Optional[str]]) -> str:
    """
    Gera um pseudônimo estável para o paciente.

    Combina rghc + cpf + nome (em minúsculas normalizadas) antes de hashear.
    Campos ausentes são substituídos por string vazia.
    """
    rghc = (ids.get("rghc") or "").strip()
    cpf  = re.sub(r'\D', '', ids.get("cpf") or "")
    nome = (ids.get("nome_paciente") or "").strip().lower()
    raw  = f"{rghc}|{cpf}|{nome}"
    return hash_text(raw)


def upsert_patient(conn, ids: Dict[str, Optional[str]]) -> str:
    """
    Garante que o paciente exista na tabela `patients`.

    Retorna o `patient_hash`.
    """
    patient_hash = compute_hash(ids)
    now = datetime.now(timezone.utc).isoformat()

    existing = conn.execute(
        "SELECT patient_hash FROM patients WHERE patient_hash = ?",
        (patient_hash,),
    ).fetchone()

    with transaction(conn):
        if existing:
            conn.execute(
                "UPDATE patients SET updated_at = ? WHERE patient_hash = ?",
                (now, patient_hash),
            )
        else:
            conn.execute(
                """INSERT INTO patients
                   (patient_hash, rghc, cpf, nome_paciente, data_nascimento,
                    first_seen_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    patient_hash,
                    ids.get("rghc"),
                    ids.get("cpf"),
                    ids.get("nome_paciente"),
                    ids.get("data_nascimento"),
                    now,
                    now,
                ),
            )

    return patient_hash


def resolve_patient(conn, patient_hash: str) -> Optional[Dict]:
    """
    Devolve os dados reais do paciente.

    **Usar apenas no Painel Seguro, após autenticação.**
    """
    row = conn.execute(
        "SELECT * FROM patients WHERE patient_hash = ?", (patient_hash,)
    ).fetchone()
    return dict(row) if row else None
