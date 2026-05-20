"""Banco lexical hierárquico (ExpandedViolenceLexicon).

Implementa a base lexical descrita na Fase 1 da metodologia do TCC: 8
categorias semânticas com pesos diferenciados por especificidade
diagnóstica (Tabela 1 da monografia).

Termos sinalizados pelos analistas como geradores de falso-positivo
("pau" isolado em "São Paulo", "machado" em sobrenomes, "DEAM" como
sigla de delegacia) foram excluídos em fase de curadoria. A versão
institucional contém 1.500 termos no NUVE/HCFMUSP; esta versão pública
expõe ~600 termos representativos suficientes para reproduzir o pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class Category:
    name: str
    weight: float
    terms: tuple


class ExpandedViolenceLexicon:

    # ---- 8 categorias da Tabela 1 do TCC ---------------------------------

    MEDICAL_FORMAL = Category("medical_formal", 2.8, (
        "trauma contundente", "trauma por força contusa", "lesão contundente",
        "trauma cranioencefálico", "tce", "traumatismo craniano", "trauma facial",
        "trauma cervical", "trauma torácico", "trauma abdominal", "politraumatismo",
        "hematoma subdural", "hematoma epidural", "hematoma intracraniano",
        "hematoma retroauricular", "hematoma periorbitário", "hematoma occipital",
        "equimose periorbital", "hematoma periorbital", "olho roxo",
        "equimoses múltiplas", "equimoses em diferentes estágios", "equimoses bilaterais",
        "hematoma em asa de borboleta", "equimoses sugestivas",
        "laceração cutânea", "laceração facial", "laceração profunda",
        "laceração do couro cabeludo", "laceração labial", "laceração genital",
        "ferimento corto-contuso", "ferimento inciso", "ferimento perfurante",
        "ferimento por arma de fogo", "ferimento por arma branca", "lesão por projétil",
        "fratura de mandíbula", "fratura maxilar", "fratura facial", "fratura nasal",
        "fratura de órbita", "fratura zigomática", "fratura do arco zigomático",
        "fratura de costela", "fraturas múltiplas", "fratura espiral",
        "fratura metafisária", "fratura em galho verde", "fratura patológica",
        "queimadura intencional", "queimadura por cigarro", "queimadura circunscrita",
        "queimadura por líquido quente", "queimadura por ferro", "queimadura em luva",
        "queimadura em meia", "queimadura com formato de objeto", "escaldadura",
        "escoriações múltiplas", "escoriações lineares", "escoriações ungueais",
        "marcas de mordida humana", "marcas de dedos", "marcas de mão",
        "marcas de corda", "marcas de estrangulamento", "marcas de amarração",
        "petéquias no pescoço", "equimoses cervicais", "sulco de enforcamento",
        "lesões de defesa", "ferimentos defensivos", "trauma não acidental",
        "lesões nas mãos", "lesões nos braços", "ferimentos por proteção",
        "violência sexual", "estupro", "abuso sexual", "trauma genital",
        "laceração vaginal", "laceração anal", "lesão himenal", "hematoma genital",
        "equimose genital", "trauma anogenital", "lesão perianal", "fissura anal",
        "negligência grave", "desnutrição proteico-calórica", "abandono de incapaz",
        "desidratação severa", "má higiene corporal", "lesões por decúbito",
        "infestação parasitária", "deficiência de cuidados", "estado de abandono",
        "transtorno de estresse pós-traumático", "tept", "depressão reativa",
        "ansiedade pós-traumática", "dissociação", "flashbacks",
        "ideação suicida", "tentativa de suicídio", "automutilação", "autoextermínio",
        "comportamento autodestrutivo", "tentativa de autolesão",
        "síndrome do bebê sacudido", "trauma craniano não acidental",
        "hemorragia retiniana", "hematoma subdural em criança",
        "síndrome de munchausen por procuração", "doença fabricada",
        "sintomas induzidos", "intoxicação induzida",
    ))

    LEGAL_POLICE = Category("legal_police", 2.5, (
        "agressão física", "agressão corporal", "violência física",
        "lesão corporal", "lesão corporal leve", "lesão corporal grave",
        "lesão corporal gravíssima", "vias de fato", "violência doméstica",
        "ameaça", "ameaça de morte", "intimidação", "ameaça grave",
        "ameaça com arma", "ameaça de espancamento", "intimidação psicológica",
        "chantagem", "extorsão", "coação", "constrangimento ilegal",
        "cárcere privado", "sequestro", "sequestro relâmpago",
        "privação de liberdade", "confinamento forçado", "aprisionamento",
        "estupro", "estupro de vulnerável", "atentado violento ao pudor",
        "assédio sexual", "abuso sexual", "exploração sexual",
        "violência sexual", "estupro conjugal", "sexo forçado",
        "homicídio", "tentativa de homicídio", "feminicídio",
        "tentativa de feminicídio", "latrocínio", "assassinato",
        "arma branca", "arma de fogo", "objeto contundente",
        "faca", "revólver", "pistola",
        "espancamento", "surra", "facada", "tiro",
        "enforcamento", "estrangulamento", "sufocamento", "asfixia",
        "envenenamento", "intoxicação proposital", "afogamento",
        "boletim de ocorrência", "b.o.", "inquérito policial",
        "termo circunstanciado", "flagrante delito", "prisão em flagrante",
        "medida protetiva de urgência", "ordem de proteção",
        "medida cautelar", "afastamento do lar",
        "exame de corpo de delito", "laudo pericial", "perícia criminal",
        "exame sexológico", "exame de conjunção carnal", "perícia médica",
    ))

    MARIA_PENHA_DOMESTIC = Category("maria_penha_domestic", 2.3, (
        "violência doméstica", "violência intrafamiliar", "violência conjugal",
        "violência de gênero", "violência contra mulher", "maus-tratos domésticos",
        "violência no lar", "agressão doméstica", "abuso doméstico",
        "feminicídio", "tentativa de feminicídio", "crime passional",
        "feminicídio íntimo", "morte violenta de mulher", "homicídio de gênero",
        "ciclo da violência", "ciclo de abuso", "escalada da violência",
        "violência repetitiva", "padrão de agressão", "histórico de violência",
        "relacionamento abusivo", "namoro violento", "parceiro abusivo",
        "companheiro violento", "marido agressor", "ex-parceiro violento",
        "violência física doméstica", "violência psicológica", "violência moral",
        "violência sexual conjugal", "violência patrimonial", "violência econômica",
        "violência institucional", "violência simbólica", "violência obstétrica",
        "controle coercitivo", "dominação psicológica", "ciúmes patológicos",
        "possessividade excessiva", "controle obsessivo", "comportamento controlador",
        "isolamento social forçado", "proibição de trabalhar", "proibição de sair",
        "proibição de estudar", "afastamento da família", "isolamento de amigos",
        "confinamento doméstico", "restrição de movimento",
        "monitoramento digital", "controle de celular", "cyberstalking",
        "violência virtual", "stalking digital", "perseguição online",
        "controle de redes sociais", "violação de privacidade digital",
        "humilhação constante", "gaslighting", "chantagem emocional",
        "manipulação psicológica", "terrorismo psicológico", "tortura psicológica",
        "ameaças constantes", "intimidação permanente", "desvalorização sistemática",
        "destruição de objetos pessoais", "controle financeiro absoluto",
        "privação de recursos", "destruição de documentos", "venda forçada de bens",
        "apropriação de salário", "chantagem financeira",
        "delegacia da mulher", "casa abrigo", "medidas protetivas",
        "centro de referência", "serviço especializado", "rede de apoio",
        "defensoria pública", "ministério público", "vara de violência doméstica",
        "lei maria da penha",
    ))

    HEALTHCARE_NURSING = Category("healthcare_nursing", 2.0, (
        "paciente relata violência", "usuário informa agressão", "refere maus-tratos",
        "história de violência", "episódios de violência", "relato de agressão",
        "menciona espancamento", "conta sobre agressão", "narra violência",
        "história pregressa de violência", "episódios anteriores de violência",
        "antecedentes de maus-tratos", "histórico de agressões",
        "violência recorrente", "agressões repetidas", "maus-tratos crônicos",
        "sinais evidentes de violência", "indícios de maus-tratos",
        "suspeita de violência doméstica", "lesões compatíveis com agressão",
        "ferimentos sugestivos", "padrão de lesões", "lesões não acidentais",
        "hematomas múltiplos", "equimoses generalizadas", "roxos pelo corpo",
        "marcas visíveis", "ferimentos em cicatrização", "lesões recentes",
        "traumatismos evidentes", "sinais de espancamento",
        "queimaduras circunscritas", "marca de cigarro", "queimadura suspeita",
        "lesão térmica intencional", "padrão de queimadura", "escaldadura proposital",
        "escoriações lineares", "arranhões defensivos", "marcas de unhas",
        "dinâmica familiar conturbada", "relacionamento conjugal conflituoso",
        "ambiente familiar violento", "tensão familiar evidente",
        "conflitos domésticos frequentes", "brigas constantes em casa",
        "filhos presenciam violência", "crianças traumatizadas",
        "menores expostos à violência", "impacto psicológico nas crianças",
        "crianças em situação de risco", "violência testemunhada",
        "comportamento de submissão", "evita contato visual", "hipervigilância",
        "medo excessivo", "ansiedade extrema", "comportamento evasivo",
        "respostas de sobressalto", "estado de alerta constante",
        "cefaleia tensional", "insônia grave", "pesadelos recorrentes",
        "distúrbios do sono",
        "notificação compulsória", "ficha de notificação de violência",
        "comunicação ao conselho tutelar", "relatório de suspeita",
        "encaminhamento para rede de proteção", "acionamento de serviços sociais",
    ))

    PSYCHOLOGICAL_ABUSE = Category("psychological_abuse", 1.9, (
        "manipulação psicológica", "chantagem emocional", "gaslighting",
        "lavagem cerebral", "distorção da realidade", "confusão mental induzida",
        "humilhação constante", "desmoralização", "diminuição sistemática",
        "rebaixamento", "vexame público", "constrangimento proposital",
        "isolamento social", "afastamento forçado", "separação de familiares",
        "privação de contatos", "confinamento emocional", "solidão forçada",
        "controle mental", "dominação psicológica", "subjugação emocional",
        "tirania doméstica", "ditadura familiar", "autoritarismo extremo",
    ))

    COLLOQUIAL_POPULAR = Category("colloquial_popular", 1.8, (
        "surra", "porrada", "pancada", "sova", "cacetada", "paulada",
        "bordoada", "tapão", "sopapo", "bicuda", "coice", "pescoção",
        "soco", "murro", "tapa", "bofetada", "cascudo", "chute", "pontapé",
        "joelhada", "cabeçada", "cotovelada", "pisão", "empurrão", "beliscão",
        "bateu na mulher", "agrediu a esposa", "espancou a companheira",
        "deu uma surra", "quebrou na porrada", "meteu a mão",
        "partiu para cima", "desceu a mão",
        "me bateu", "apanhei dele", "levei surra", "me deu porrada",
        "me agrediu", "me espancou", "bateu em mim", "me machucou",
        "me fez mal", "me maltratou", "me judiou",
        "ameaçou me matar", "disse que me mata", "prometeu me acabar",
        "falou que ia me quebrar", "ameaçou me dar uma surra",
        "disse que ia me bater", "prometeu me machucar",
        "muito ciumento", "não deixa sair", "controla tudo", "mexe no celular",
        "não deixa trabalhar", "vigia sempre", "segue para todo lado",
        "não deixa ter amigos", "proíbe de sair", "controla o dinheiro",
        "morro de medo dele", "não aguento mais", "vivo com medo",
        "tenho pavor", "não posso contrariá-lo", "ando nas pontas dos pés",
        "me forçou", "me obrigou", "não aceitou não", "forçou a barra",
        "não respeitou minha vontade", "fez à força", "me violentou",
        "briga de casal", "confusão em casa", "barraco em casa",
        "discussão feia", "briga violenta",
        "bebe e fica violento", "viciado agressivo",
        "alcoolizado violento", "fica alterado quando usa",
        "tacou objeto", "jogou coisa", "atirou na parede",
        "quebrou tudo", "destruiu a casa", "fez estrago",
        "ficou todo roxo", "marcou o rosto", "deixou marca",
        "saiu sangue", "inchou o olho", "ficou desfigurado",
    ))

    ORTHOGRAPHIC_VARIATIONS = Category("orthographic_variations", 1.5, (
        "agressão", "agreção", "agressao", "agresão", "agrediu", "agridiu",
        "agredindo", "agridindo", "agressor", "agresor", "agressivo", "agresivo",
        "violência", "violencia", "violensia", "violensa", "violento", "violênto",
        "violenta", "violentou", "violentando",
        "espancamento", "spancamento", "espancou", "espancada",
        "spancada", "espancando", "espancar",
        "machucou", "machukou", "machucado", "machucada", "machucando", "machucar",
        "bateu", "batêu", "batendo", "bater",
        "ameaçou", "ameaçando", "ameaça", "ameasa",
        "judiou", "judiar", "maltratou", "forçou", "forçar", "obrigou",
    ))

    CHILD_SPECIFIC = Category("child_specific", 2.7, (
        "maus-tratos infantis", "abuso infantil", "negligência infantil",
        "violência contra criança", "agressão a menor", "maltrato infantil",
        "síndrome do bebê sacudido", "trauma craniano não acidental em criança",
        "lesões não acidentais em menor", "padrão de lesões em criança",
        "negligência de cuidados básicos", "privação de alimentos", "falta de higiene",
        "ausência de cuidados médicos", "abandono de incapaz",
        "criança em situação de risco",
    ))

    # ---- Padrões auxiliares (negação, evasão, contextos críticos) --------

    NEGATION_TRIGGERS = (
        "não", "nao", "jamais", "nunca", "nega", "negou", "descarta",
        "afasta", "exclui", "ausente", "sem", "inexistente", "improvável",
        "sem evidências", "sem indícios", "sem sinais", "descartado",
    )

    EVASION_MARKERS = (
        "não quis detalhar", "não quis comentar", "história inconsistente",
        "não soube precisar", "evita responder", "responde por paciente",
        "acompanhante controla", "paciente em silêncio",
    )

    # Pesos de bônus de padrões críticos (também usados em config.PATTERN_BONUSES)
    CRITICAL_KEYWORDS = {
        "weapons": ("faca", "revólver", "pistola", "arma de fogo", "arma branca",
                    "facão", "canivete", "estilete", "punhal"),  # 'pau','machado' removidos
        "death_threats": ("vou te matar", "vai morrer", "ameaçou de morte",
                          "disse que ia matar", "prometeu matar", "falou em matar"),
        "pregnancy": ("grávida", "gestante", "gravidez", "gestação",
                      "chutou barriga", "pancada na barriga"),
        "children_present": ("na frente das crianças", "criança viu", "filho assistiu",
                             "menor presenciou", "na presença dos filhos",
                             "crianças viram"),
        "sexual": ("estupro", "abuso sexual", "violência sexual", "sexo forçado",
                   "violentou sexualmente", "estupro de vulnerável"),
        "chronic": ("sempre", "todo dia", "constantemente", "anos", "rotina",
                    "frequentemente", "diariamente", "há tempos", "há anos",
                    "desde pequena"),
        "escalation": ("piorou", "aumentou", "cada vez mais", "ficou pior",
                       "está pior", "mais violento", "mais agressivo",
                       "perdeu o controle"),
        "psychological_control": ("não deixa sair", "controla tudo", "vigia sempre",
                                  "ciúme doentio", "possessivo", "controlador",
                                  "não deixa trabalhar", "mexe no celular"),
        "economic_abuse": ("não dá dinheiro", "controla dinheiro",
                           "esconde dinheiro", "controle financeiro",
                           "privação econômica"),
    }

    INJURY_TERMS = ("hematoma", "corte", "fratura", "roxo", "sangue",
                    "equimose", "escoriação", "laceração", "ferimento", "lesão")

    # ---- API ------------------------------------------------------------

    @classmethod
    def all_categories(cls) -> list[Category]:
        return [
            cls.MEDICAL_FORMAL, cls.LEGAL_POLICE, cls.MARIA_PENHA_DOMESTIC,
            cls.HEALTHCARE_NURSING, cls.PSYCHOLOGICAL_ABUSE, cls.COLLOQUIAL_POPULAR,
            cls.ORTHOGRAPHIC_VARIATIONS, cls.CHILD_SPECIFIC,
        ]

    @classmethod
    def flat_terms(cls):
        for cat in cls.all_categories():
            for term in cat.terms:
                yield term, cat.name, cat.weight

    @classmethod
    def total_terms(cls) -> int:
        return sum(len(c.terms) for c in cls.all_categories())

    @classmethod
    def stats(cls) -> dict:
        return {c.name: {"weight": c.weight, "n": len(c.terms)}
                for c in cls.all_categories()}


def compile_term_patterns() -> list[tuple[Pattern, str, str, float]]:
    """Compila regex word-boundary por termo, retornando (regex, term, category, weight)."""
    compiled = []
    for term, category, weight in ExpandedViolenceLexicon.flat_terms():
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        compiled.append((pattern, term, category, weight))
    return compiled


def compile_negation_patterns() -> list[Pattern]:
    """Padrões de negação descritos na metodologia (janela ~80 chars antes)."""
    base = r"\b(?:viol|agred|espanc|machuc|bat|surr|ameaç|mal.?trat)\w*"
    return [
        re.compile(rf"\b{re.escape(trig)}\b[\s\w]{{0,80}}{base}", re.IGNORECASE)
        for trig in ExpandedViolenceLexicon.NEGATION_TRIGGERS
    ]
