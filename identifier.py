"""EnhancedPatientIdentifier — extração e anonimização de identificadores.

Política descrita na metodologia (HIPAA Safe Harbor):
  - RGHC: mantida íntegra (chave institucional para auditoria)
  - CPF:  parcial (3 primeiros + *** + 3 últimos dígitos)
  - Nome: preservado para contexto clínico
  - Hash determinístico (salt + base_id) gera o pseudônimo PAC_XXXX
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import ProcessingConfig

_PATTERNS = {
    "RGHC": re.compile(r"(?:RGHC|Registro|Prontuário|HC)[\s:\-#]*(\d{6,12})", re.IGNORECASE),
    "CODIGO_PACIENTE": re.compile(r"(?:Código|Cod\.?|ID)[\s:\-#]*(?:Paciente)?[\s:\-#]*(\w{3,15})", re.IGNORECASE),
    "MATRICULA": re.compile(r"(?:Matrícula|Mat\.?)[\s:\-#]*(\d{4,12})", re.IGNORECASE),
    "CPF": re.compile(r"(?:CPF)[\s:\-#]*(\d{3}\.?\d{3}\.?\d{3}\-?\d{2})", re.IGNORECASE),
    "DATA_NASCIMENTO": re.compile(r"(?:Data\s+de\s+)?(?:Nascimento|Nasc\.?|DN)[\s:\-#]*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})", re.IGNORECASE),
    "NOME_COMPLETO": re.compile(r"(?:Nome[\s\-]?(?:do[\s\-]?)?Paciente|Paciente)[\s:]+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,4})"),
    "NOME_ALTERNATIVO": re.compile(r"Nome:?\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+){1,4})"),
}

_FILENAME_NUMBER = re.compile(r"(?<!\d)(\d{6,10})(?!\d)")
_ANON_SALT = "NUVE_NOTIFICAI_2024"


@dataclass
class PatientIdentifier:
    patient_id: str
    document_hash: str
    filename: str
    rghc: Optional[str] = None
    codigo_paciente: Optional[str] = None
    cpf: Optional[str] = None
    data_nascimento: Optional[str] = None
    nome_paciente: Optional[str] = None
    extracted_raw: dict = field(default_factory=dict)


def _mask_cpf(cpf: str) -> str:
    digits = re.sub(r"\D", "", cpf)
    if len(digits) >= 6:
        return f"{digits[:3]}***{digits[-3:]}"
    return cpf


def _generate_patient_id(base: str) -> str:
    h = hashlib.sha256(f"{_ANON_SALT}|{base}".encode("utf-8")).hexdigest()[:12]
    return f"PAC_{h.upper()}"


class EnhancedPatientIdentifier:
    def __init__(self, config: ProcessingConfig | None = None):
        self.config = config or ProcessingConfig()

    def extract(self, text: str, source_filename: str | None = None) -> PatientIdentifier:
        header = text[:2000]
        raw: dict[str, str] = {}
        for key, pattern in _PATTERNS.items():
            m = pattern.search(header)
            if m:
                raw[key] = m.group(1).strip()

        rghc = raw.get("RGHC")
        codigo = raw.get("CODIGO_PACIENTE") or raw.get("MATRICULA")
        cpf_raw = raw.get("CPF")
        nome = raw.get("NOME_COMPLETO") or raw.get("NOME_ALTERNATIVO")
        dn = raw.get("DATA_NASCIMENTO")

        file_id = None
        if source_filename:
            m = _FILENAME_NUMBER.search(Path(source_filename).stem)
            if m:
                file_id = m.group(1)

        doc_hash = hashlib.sha256(
            f"{source_filename or ''}|{text[:1000]}".encode("utf-8")
        ).hexdigest()[:16]

        base = rghc or codigo or file_id or doc_hash
        patient_id = _generate_patient_id(base) if self.config.anonymize_identifiers else base

        cpf_out = _mask_cpf(cpf_raw) if (cpf_raw and self.config.anonymize_identifiers) else cpf_raw
        codigo_out = (("***" + codigo[-3:]) if (codigo and self.config.anonymize_identifiers and len(codigo) > 3)
                      else codigo)

        return PatientIdentifier(
            patient_id=patient_id,
            document_hash=doc_hash,
            filename=Path(source_filename).name if source_filename else "",
            rghc=rghc,
            codigo_paciente=codigo_out,
            cpf=cpf_out,
            data_nascimento=dn,
            nome_paciente=nome,
            extracted_raw=raw,
        )
