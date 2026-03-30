"""
nlp/ner.py
==========
Extração de Entidades Nomeadas (NER) orientada a prontuários brasileiros.

Responsabilidade única: dado um texto clínico, retornar quais identificadores
de paciente foram encontrados e em que posição.

Estratégia híbrida (em ordem de prioridade):
  1. Regex determinístico  → CPF, RGHC, datas de nascimento, matrícula
  2. Heurística de nome    → padrões "Paciente: João Silva" / "Nome: ..."
  3. spaCy (opcional)      → modelo pt_core_news_sm para NER geral
     (ativado só se o modelo estiver instalado)

Saída garantida: sempre um PatientEntities, mesmo que vazio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PatientEntities:
    """
    Entidades de identificação do paciente extraídas do texto.
    Vinculadas a cada DetectionResult para garantir rastreabilidade.
    """
    nome: Optional[str] = None
    cpf: Optional[str] = None
    rghc: Optional[str] = None           # Registro Geral do HC (USP/FMUSP)
    matricula: Optional[str] = None
    data_nascimento: Optional[str] = None
    idade: Optional[str] = None
    sexo: Optional[str] = None
    raw_matches: List[dict] = field(default_factory=list)  # Para auditoria

    @property
    def primary_id(self) -> str:
        """Retorna o melhor identificador disponível para exibição."""
        return (
            self.rghc
            or self.cpf
            or self.matricula
            or self.nome
            or "Paciente não identificado"
        )

    @property
    def has_any(self) -> bool:
        return any([self.nome, self.cpf, self.rghc, self.matricula])


# ---------------------------------------------------------------------------
# Padrões regex — ajustados para prontuários do HCFMUSP e padrão SINAN
# ---------------------------------------------------------------------------

_PATTERNS = {
    # CPF: 000.000.000-00 ou 00000000000
    "cpf": re.compile(
        r'\b(?:CPF|C\.P\.F\.?)[:\s]*(\d{3}[\.\-]?\d{3}[\.\-]?\d{3}[\.\-]?\d{2})\b',
        re.IGNORECASE,
    ),
    # RGHC / Registro HC
    "rghc": re.compile(
        r'\b(?:RGHC|RG\.?H\.?C\.?|Registro\s+(?:HC|Geral)|Prontuário|Pront\.?)[:\s#Nº°]*(\d{4,12})\b',
        re.IGNORECASE,
    ),
    # Matrícula / número interno
    "matricula": re.compile(
        r'\b(?:Matr[íi]cula|Mat\.|Código\s+Paciente|Cód\.?\s+Pac\.?)[:\s#Nº°]*([A-Z0-9\-]{4,15})\b',
        re.IGNORECASE,
    ),
    # Nome do paciente (vários padrões de cabeçalho de prontuário)
    "nome": re.compile(
        r'(?:Paciente|Nome|Pt\.?|PAC\.?)\s*[:\-]\s*([A-ZÀ-Ú][a-zA-ZÀ-ÿ\s]{3,50})(?=\n|,|\||Data|CPF|RG|Nasc)',
        re.IGNORECASE,
    ),
    # Data de nascimento
    "data_nascimento": re.compile(
        r'\b(?:Nasc\.?(?:imento)?|DN|D\.N\.)[:\s]*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b',
        re.IGNORECASE,
    ),
    # Idade
    "idade": re.compile(
        r'\b(?:Idade|Id\.?)[:\s]*(\d{1,3})\s*(?:anos?|a\.)\b',
        re.IGNORECASE,
    ),
    # Sexo / gênero
    "sexo": re.compile(
        r'\b(?:Sexo|Gênero|Sex\.?)[:\s]*(Masculino|Feminino|Masc\.?|Fem\.?|M|F)\b',
        re.IGNORECASE,
    ),
}


class PatientNER:
    """
    Extrator de entidades de pacientes para textos clínicos em português.

    Uso:
        ner = PatientNER()
        entities = ner.extract("Paciente: Maria da Silva | RGHC: 12345678 | CPF: 123.456.789-00")
        print(entities.primary_id)   # "12345678"
    """

    def __init__(self, use_spacy: bool = True):
        self._spacy_nlp = None
        if use_spacy:
            self._try_load_spacy()

    def _try_load_spacy(self) -> None:
        try:
            import spacy
            self._spacy_nlp = spacy.load("pt_core_news_sm")
        except Exception:
            # spaCy é opcional — regex cobre a maior parte dos casos
            pass

    def extract(self, text: str) -> PatientEntities:
        """Extrai entidades do texto e retorna PatientEntities."""
        entities = PatientEntities()
        raw_matches: list = []

        # --- Passo 1: Regex determinístico ---
        for field_name, pattern in _PATTERNS.items():
            match = pattern.search(text)
            if match:
                value = match.group(1).strip()
                setattr(entities, field_name, value)
                raw_matches.append({
                    "field": field_name,
                    "value": value,
                    "span": match.span(),
                    "method": "regex",
                })

        # --- Passo 2: spaCy (complementa, não substitui) ---
        if self._spacy_nlp and not entities.nome:
            spacy_name = self._extract_name_spacy(text)
            if spacy_name:
                entities.nome = spacy_name
                raw_matches.append({
                    "field": "nome",
                    "value": spacy_name,
                    "method": "spacy",
                })

        entities.raw_matches = raw_matches
        return entities

    def _extract_name_spacy(self, text: str) -> Optional[str]:
        """Usa spaCy para encontrar entidades do tipo PER (pessoa)."""
        try:
            doc = self._spacy_nlp(text[:2000])  # Limita para performance
            persons = [ent.text for ent in doc.ents if ent.label_ == "PER"]
            # Retorna o primeiro nome que parece plausível (>= 2 tokens)
            for p in persons:
                if len(p.split()) >= 2:
                    return p
        except Exception:
            pass
        return None
