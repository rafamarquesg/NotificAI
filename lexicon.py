"""Banco lexical hierárquico de violência (ExpandedViolenceLexicon).

Implementa o léxico descrito na Fase 1 da metodologia do TCC: 8 categorias
semânticas com pesos diferenciados por especificidade diagnóstica. O léxico
completo institucional contém 1.500 termos (versão final); este arquivo
contém amostra representativa de domínio público suficiente para reproduzir
o pipeline e a metodologia. A versão completa pode ser disponibilizada
mediante solicitação institucional ao NUVE/HCFMUSP.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Category:
    name: str
    weight: float
    terms: tuple


class ExpandedViolenceLexicon:
    TERMOS_MEDICOS_FORMAIS = Category(
        name="termos_medicos_formais",
        weight=2.8,
        terms=(
            "trauma contundente", "tce por agressão", "lesão por objeto contundente",
            "hematoma", "equimose", "fratura", "tce", "ferimento corto-contuso",
            "lesão por arma branca", "queimadura suspeita", "trauma cranioencefálico",
            "hematoma subdural", "fratura de arcos costais", "equimose periorbital",
            "ferimento perfurocontuso", "lesão por arma de fogo", "lesões em diferentes estágios",
            "lacerações múltiplas", "trauma facial", "fratura nasal", "luxação",
            "abrasão", "contusão", "escoriação", "ferida lacerocontusa",
            "trauma toracoabdominal", "fratura de mandíbula", "dente avulsionado",
            "perfuração timpânica", "sinal do guaxinim", "sinal de battle",
        ),
    )

    VIOLENCIA_INFANTIL = Category(
        name="violencia_infantil",
        weight=2.7,
        terms=(
            "síndrome do bebê sacudido", "abuso infantil", "maus-tratos",
            "negligência infantil", "shaken baby", "trauma não-acidental",
            "abuso sexual infantil", "pedofilia", "estupro de vulnerável",
            "exploração sexual infantil", "trabalho infantil", "fratura em criança menor de 2 anos",
            "queimadura por imersão", "lesão em padrão de mordida humana",
            "fratura espiral em lactente", "hematoma em criança não-deambuladora",
            "criança em situação de risco", "abandono de incapaz",
            "lesão por cigarro", "marca de cinta", "marca de fio",
            "atraso no desenvolvimento por privação", "desnutrição por negligência",
            "criança presente durante violência",
        ),
    )

    TERMINOLOGIA_LEGAL_POLICIAL = Category(
        name="terminologia_legal_policial",
        weight=2.5,
        terms=(
            "agressão física", "lesão corporal", "vias de fato", "ameaça",
            "boletim de ocorrência", "delegacia da mulher", "registro de ocorrência",
            "lesão corporal dolosa", "tentativa de homicídio", "homicídio",
            "porte de arma", "constrangimento ilegal", "cárcere privado",
            "sequestro", "lesão corporal grave", "lesão corporal gravíssima",
            "tortura", "agressor", "vítima de agressão", "perpetrador",
            "denúncia anônima", "ligue 180", "disque 100", "disque 190",
            "iml", "instituto médico legal", "perícia criminal",
        ),
    )

    VIOLENCIA_DOMESTICA = Category(
        name="violencia_domestica_maria_penha",
        weight=2.3,
        terms=(
            "violência doméstica", "feminicídio", "lei maria da penha",
            "violência por parceiro íntimo", "vpi", "violência conjugal",
            "violência intrafamiliar", "agressão pelo companheiro",
            "agressão pelo marido", "agressão pelo ex-companheiro",
            "medida protetiva", "afastamento do agressor", "violência de gênero",
            "ciclo de violência", "violência patrimonial", "violência moral",
            "relação abusiva", "casa abrigo", "centro de referência da mulher",
            "ceam", "centro de referência de atendimento à mulher",
            "ameaça pelo companheiro", "violência contra a mulher",
        ),
    )

    CONTEXTOS_ENFERMAGEM = Category(
        name="contextos_enfermagem",
        weight=2.0,
        terms=(
            "paciente relata violência", "sinais de maus-tratos", "maus-tratos",
            "paciente refere agressão", "paciente nega, mas...",
            "história inconsistente", "mecanismo de trauma incompatível",
            "paciente chorosa", "paciente apreensiva", "paciente intimidada",
            "acompanhante responde por paciente", "acompanhante controlador",
            "paciente evita contato visual", "paciente em mutismo",
            "relato de agressão", "história de violência prévia",
            "atendimentos repetidos por trauma", "recusa exame ginecológico",
            "paciente sob coação aparente", "sinais de violência psicológica",
            "comportamento submisso", "medo de retornar ao domicílio",
        ),
    )

    ABUSO_PSICOLOGICO = Category(
        name="abuso_psicologico",
        weight=1.9,
        terms=(
            "gaslighting", "controle coercitivo", "isolamento social",
            "humilhação constante", "manipulação emocional", "chantagem emocional",
            "ameaça verbal", "intimidação", "perseguição", "stalking",
            "ciúme patológico", "controle financeiro", "violência financeira",
            "depreciação", "menosprezo", "xingamentos constantes",
            "monitoramento excessivo", "privação de liberdade",
            "isolamento da família", "isolamento de amigos",
            "destruição de objetos pessoais", "ameaça de suicídio do parceiro",
            "violência psicológica",
        ),
    )

    LINGUAGEM_COLOQUIAL = Category(
        name="linguagem_coloquial",
        weight=1.8,
        terms=(
            "apanhou", "levou uma surra", "foi agredido", "espancamento",
            "espancado", "espancada", "tomou um pau", "saiu no braço",
            "levou um murro", "levou um tapa", "levou uma porrada",
            "foi atacado", "foi atacada", "foi espancado", "foi espancada",
            "deu uma surra", "bateu na esposa", "bateu na mulher",
            "bateu no filho", "deu uns tapas", "se desentenderam",
            "se atracaram", "trocaram socos", "agarraram pelo cabelo",
            "foi puxado pelos cabelos", "foi arrastado", "foi arrastada",
            "deu um chute", "chutaram", "socaram",
        ),
    )

    VARIACOES_ORTOGRAFICAS = Category(
        name="variacoes_ortograficas",
        weight=1.5,
        terms=(
            "agreção", "agreçao", "violencia", "violenca", "agreçoes",
            "espancamento", "espancameto", "espancamneto", "epancamento",
            "agressão fisica", "lesão coporal", "lesao corporal", "lesao corpoarl",
            "feminicidio", "feminicídeo", "maus tratos", "maustratos",
            "ameça", "amaeça", "ameasa", "violensia",
            "agreciu", "agredeu", "vitima", "victima",
        ),
    )

    VIOLENCIA_SEXUAL = Category(
        name="violencia_sexual",
        weight=2.8,
        terms=(
            "estupro", "violência sexual", "abuso sexual", "violação sexual",
            "atentado violento ao pudor", "estupro de vulnerável",
            "coação sexual", "sexo forçado", "relação sexual não consensual",
            "exploração sexual", "assédio sexual", "importunação sexual",
            "ato libidinoso", "kit estupro", "profilaxia pós-exposição sexual",
            "anticoncepção de emergência", "pep sexual",
            "exame de conjunção carnal", "vestígios de violência sexual",
            "lesão genital", "trauma genital", "trauma anal não acidental",
            "ist por violência sexual", "ist pós-violência",
        ),
    )

    @classmethod
    def all_categories(cls):
        return [
            cls.TERMOS_MEDICOS_FORMAIS,
            cls.VIOLENCIA_INFANTIL,
            cls.TERMINOLOGIA_LEGAL_POLICIAL,
            cls.VIOLENCIA_DOMESTICA,
            cls.CONTEXTOS_ENFERMAGEM,
            cls.ABUSO_PSICOLOGICO,
            cls.LINGUAGEM_COLOQUIAL,
            cls.VARIACOES_ORTOGRAFICAS,
            cls.VIOLENCIA_SEXUAL,
        ]

    @classmethod
    def flat_terms(cls):
        out = []
        for cat in cls.all_categories():
            for term in cat.terms:
                out.append((term, cat.name, cat.weight))
        return out

    @classmethod
    def stats(cls):
        return {cat.name: {"weight": cat.weight, "n": len(cat.terms)} for cat in cls.all_categories()}


NEGATION_TRIGGERS = ("não", "nao", "nega", "negou", "descarta", "descartado",
                     "ausente", "ausência", "sem sinais", "sem evidência",
                     "sem evidencia", "rejeita")

EVASION_MARKERS = ("não quis detalhar", "não quis comentar", "história inconsistente",
                   "não soube precisar", "evita responder", "responde por paciente",
                   "acompanhante controla", "paciente em silêncio")

CRITICAL_PATTERNS = {
    "violencia_cronica": (2.0, ("atendimentos repetidos", "história de agressão prévia",
                                 "violência recorrente", "agressões frequentes")),
    "armas": (3.0, ("arma de fogo", "arma branca", "faca", "revólver", "pistola")),
    "ameacas": (3.0, ("ameaça de morte", "ameaçou matar", "promete matar")),
    "violencia_gravidez": (3.5, ("gestante agredida", "agressão na gravidez",
                                  "violência durante gestação")),
    "criancas_presentes": (2.5, ("criança presenciou", "filhos presentes",
                                  "menor testemunhou")),
    "violencia_sexual": (4.0, ("estupro", "violência sexual", "abuso sexual",
                                "atentado violento ao pudor")),
}
