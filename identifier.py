"""EnhancedPatientIdentifier — extração de identificadores com anonimização.

Política descrita na metodologia (HIPAA Safe Harbor):
  - Matrícula: mantida íntegra (chave institucional)
  - CPF:       anonimizado parcialmente (3 primeiros + 3 últimos dígitos)
  - Nome:      preservado para contexto clínico (uso restrito)
  - Hash único gerado por matrícula para rastreabilidade anônima
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

MATRICULA_RE = re.compile(r"\b(?:matr[ií]cula|prontu[áa]rio|reg(?:istro)?)[\s:#.\-]*([0-9]{5,10})\b", re.IGNORECASE)
MATRICULA_FILENAME_RE = re.compile(r"(?<!\d)(\d{6,10})(?!\d)")
CPF_RE = re.compile(r"\b(\d{3})\.?(\d{3})\.?(\d{3})[-\s]?(\d{2})\b")
NAME_RE = re.compile(r"(?:nome|paciente)[\s:]+([A-ZÁ-Ú][A-Za-zá-ú]+(?:\s+[A-ZÁ-Ú][A-Za-zá-ú]+){1,5})")
DOB_RE = re.compile(r"(?:nascim(?:ento)?|dn|d\.n\.)[\s:]*([0-3]?\d[/.-][0-1]?\d[/.-]\d{2,4})", re.IGNORECASE)


@dataclass
class PatientId:
    matricula: str | None
    cpf_masked: str | None
    name: str | None
    dob: str | None
    anon_hash: str


def _hash(matricula: str | None, name: str | None) -> str:
    seed = (matricula or "") + "|" + (name or "")
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


class EnhancedPatientIdentifier:
    def extract(self, text: str, source_filename: str | None = None) -> PatientId:
        matricula = None
        m = MATRICULA_RE.search(text)
        if m:
            matricula = m.group(1)
        elif source_filename:
            fm = MATRICULA_FILENAME_RE.search(Path(source_filename).stem)
            if fm:
                matricula = fm.group(1)

        cpf = CPF_RE.search(text)
        cpf_masked = f"{cpf.group(1)}.***.***-{cpf.group(4)}" if cpf else None

        name_match = NAME_RE.search(text)
        name = name_match.group(1).strip() if name_match else None

        dob_match = DOB_RE.search(text)
        dob = dob_match.group(1) if dob_match else None

        return PatientId(
            matricula=matricula,
            cpf_masked=cpf_masked,
            name=name,
            dob=dob,
            anon_hash=_hash(matricula, name),
        )
