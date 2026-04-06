"""
Léxico hierárquico para detecção de violência em prontuários médicos.

Organizado em 8 categorias especializadas, cada uma com um peso que
reflete a especificidade clínica/legal do termo.
"""

VIOLENCE_LEXICON: dict = {
    # ------------------------------------------------------------------ #
    # Terminologia médica formal de trauma (maior especificidade clínica) #
    # ------------------------------------------------------------------ #
    "medical_formal": {
        "weight": 2.8,
        "terms": [
            "trauma contundente", "trauma por força contusa", "lesão contundente",
            "trauma cranioencefálico", "TCE", "traumatismo craniano", "trauma facial",
            "trauma cervical", "trauma torácico", "trauma abdominal", "politraumatismo",
            "hematoma subdural", "hematoma epidural", "hematoma intracraniano",
            "hematoma retroauricular", "hematoma periorbitário", "hematoma occipital",
            "equimose periorbital", "hematoma periorbital", "olho roxo", "olho negro",
            "equimoses múltiplas", "equimoses em diferentes estágios", "equimoses bilaterais",
            "laceração cutânea", "laceração facial", "laceração profunda",
            "laceração do couro cabeludo", "laceração labial", "laceração genital",
            "ferimento corto-contuso", "ferimento inciso", "ferimento perfurante",
            "ferimento por arma de fogo", "ferimento por arma branca", "lesão por projétil",
            "fratura de mandíbula", "fratura maxilar", "fratura facial", "fratura nasal",
            "fratura de órbita", "fratura zigomática", "fratura do arco zigomático",
            "fratura de costela", "fraturas múltiplas", "fratura espiral",
            "queimadura intencional", "queimadura por cigarro", "queimadura circunscrita",
            "queimadura por líquido quente", "queimadura por ferro", "queimadura em luva",
            "escoriações múltiplas", "escoriações lineares", "escoriações ungueais",
            "marcas de mordida humana", "marcas de dedos", "marcas de mão",
            "marcas de corda", "marcas de estrangulamento", "marcas de amarração",
            "petéquias no pescoço", "equimoses cervicais", "sulco de enforcamento",
            "lesões de defesa", "ferimentos defensivos", "trauma não acidental",
            "violência sexual", "estupro", "abuso sexual", "trauma genital",
            "laceração vaginal", "laceração anal", "lesão himenal", "hematoma genital",
            "negligência grave", "desnutrição proteico-calórica", "abandono de incapaz",
            "desidratação severa", "má higiene corporal", "lesões por decúbito",
            "transtorno de estresse pós-traumático", "TEPT", "depressão reativa",
            "ansiedade pós-traumática", "dissociação", "flashbacks",
            "ideação suicida", "tentativa de suicídio", "automutilação", "autoextermínio",
            "comportamento autodestrutivo", "tentativa de autolesão",
            "síndrome do bebê sacudido", "trauma craniano não acidental",
            "hemorragia retiniana", "hematoma subdural em criança",
        ],
    },

    # ------------------------------------------------------------------ #
    # Terminologia jurídica e policial                                     #
    # ------------------------------------------------------------------ #
    "legal_police": {
        "weight": 2.5,
        "terms": [
            "agressão física", "agressão corporal", "violência física",
            "lesão corporal", "lesão corporal leve", "lesão corporal grave",
            "lesão corporal gravíssima", "vias de fato", "violência doméstica",
            "ameaça", "ameaça de morte", "intimidação", "ameaça grave",
            "ameaça com arma", "ameaça de espancamento", "intimidação psicológica",
            "chantagem", "extorsão", "coação", "constrangimento ilegal",
            "cárcere privado", "sequestro", "sequestro relâmpago",
            "privação de liberdade", "confinamento forçado", "aprisionamento",
            "estupro de vulnerável", "atentado violento ao pudor",
            "assédio sexual", "exploração sexual", "estupro conjugal", "sexo forçado",
            "homicídio", "tentativa de homicídio", "feminicídio",
            "tentativa de feminicídio", "latrocínio", "assassinato",
            "arma branca", "arma de fogo", "objeto contundente",
            "faca", "revólver", "pistola", "martelo",
            "bastão", "cassetete", "pedra", "tijolo",
            "espancamento", "surra", "paulada", "facada", "tiro",
            "enforcamento", "estrangulamento", "sufocamento", "asfixia",
            "boletim de ocorrência", "inquérito policial",
            "termo circunstanciado", "flagrante delito", "prisão em flagrante",
            "medida protetiva de urgência", "ordem de proteção",
            "exame de corpo de delito", "laudo pericial", "perícia criminal",
        ],
    },

    # ------------------------------------------------------------------ #
    # Violência doméstica / Lei Maria da Penha                            #
    # ------------------------------------------------------------------ #
    "maria_penha_domestic": {
        "weight": 2.3,
        "terms": [
            "violência doméstica", "violência intrafamiliar", "violência conjugal",
            "violência de gênero", "violência contra mulher", "maus-tratos domésticos",
            "violência no lar", "agressão doméstica", "abuso doméstico",
            "crime passional", "ciclo da violência", "ciclo de abuso",
            "escalada da violência", "violência repetitiva", "padrão de agressão",
            "histórico de violência", "relacionamento abusivo", "namoro violento",
            "parceiro abusivo", "companheiro violento", "marido agressor",
            "ex-parceiro violento", "violência física doméstica",
            "violência psicológica", "violência moral",
            "violência sexual conjugal", "violência patrimonial", "violência econômica",
            "controle coercitivo", "dominação psicológica", "ciúmes patológicos",
            "possessividade excessiva", "controle obsessivo", "comportamento controlador",
            "isolamento social forçado", "proibição de trabalhar", "proibição de sair",
            "proibição de estudar", "afastamento da família", "isolamento de amigos",
            "monitoramento digital", "controle de celular", "cyberstalking",
            "violência virtual", "stalking digital", "perseguição online",
            "humilhação constante", "gaslighting", "chantagem emocional",
            "manipulação psicológica", "terrorismo psicológico", "tortura psicológica",
            "destruição de objetos pessoais", "controle financeiro absoluto",
            "privação de recursos", "destruição de documentos",
            "delegacia da mulher", "casa abrigo", "medidas protetivas",
            "centro de referência",
        ],
    },

    # ------------------------------------------------------------------ #
    # Registros clínicos e de enfermagem                                  #
    # ------------------------------------------------------------------ #
    "healthcare_nursing": {
        "weight": 2.0,
        "terms": [
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
            "queimaduras circunscritas", "marca de cigarro", "queimadura suspeita",
            "escoriações lineares", "arranhões defensivos", "marcas de unhas",
            "dinâmica familiar conturbada", "relacionamento conjugal conflituoso",
            "ambiente familiar violento", "tensão familiar evidente",
            "filhos presenciam violência", "crianças traumatizadas",
            "menores expostos à violência", "impacto psicológico nas crianças",
            "comportamento de submissão", "evita contato visual", "hipervigilância",
            "medo excessivo", "ansiedade extrema", "comportamento evasivo",
            "tremores generalizados", "sudorese profusa", "taquicardia",
            "notificação compulsória", "ficha de notificação de violência",
            "comunicação ao conselho tutelar", "relatório de suspeita",
        ],
    },

    # ------------------------------------------------------------------ #
    # Linguagem coloquial / popular                                        #
    # ------------------------------------------------------------------ #
    "colloquial_popular": {
        "weight": 1.8,
        "terms": [
            "porrada", "pancada", "sova", "cacetada", "bordoada",
            "tapão", "sopapo", "bicuda", "coice", "pescoção",
            "soco", "murro", "tapa", "bofetada", "cascudo", "chute", "pontapé",
            "joelhada", "cabeçada", "cotovelada", "pisão", "empurrão", "beliscão",
            "bateu na mulher", "agrediu a esposa", "espancou a companheira",
            "deu uma surra", "quebrou na porrada", "meteu a mão",
            "me bateu", "apanhei dele", "levei surra", "me deu porrada",
            "me agrediu", "me espancou", "bateu em mim", "me machucou",
            "ameaçou me matar", "disse que me mata", "prometeu me acabar",
            "falou que ia me quebrar", "ameaçou me dar uma surra",
            "muito ciumento", "não deixa sair", "controla tudo", "mexe no celular",
            "não deixa trabalhar", "vigia sempre", "segue para todo lado",
            "me forçou", "me obrigou", "não aceitou não", "forçou a barra",
            "briga de casal", "confusão em casa", "quebra-pau em casa",
            "barraco em casa", "discussão feia", "briga violenta",
            "bebe e fica violento", "viciado agressivo",
            "tacou objeto", "jogou coisa", "atirou na parede",
            "ficou todo roxo", "marcou o rosto", "deixou marca",
        ],
    },

    # ------------------------------------------------------------------ #
    # Variações ortográficas / grafias alternativas                       #
    # ------------------------------------------------------------------ #
    "orthographic_variations": {
        "weight": 1.5,
        "terms": [
            "agreção", "agressao", "agresão", "agrediu", "agridiu",
            "agredindo", "agridindo", "agresor", "agresivo",
            "violencia", "violensia", "violensa", "violênto",
            "spancamento", "espancou", "espankou", "espancada",
            "machukou", "machucu", "machucado", "machucada",
            "batêu", "batu", "batendo", "bateno", "batê",
            "ameaçô", "ameaço", "ameaçando", "ameaçano", "ameasa",
            "judiou", "judiô", "judiar", "judiá", "maltratou", "maltrató",
        ],
    },

    # ------------------------------------------------------------------ #
    # Abuso psicológico                                                    #
    # ------------------------------------------------------------------ #
    "psychological_abuse": {
        "weight": 1.9,
        "terms": [
            "lavagem cerebral", "distorção da realidade", "confusão mental induzida",
            "humilhação constante", "desmoralização", "diminuição sistemática",
            "isolamento social", "afastamento forçado", "separação de familiares",
            "controle mental", "dominação psicológica", "subjugação emocional",
        ],
    },

    # ------------------------------------------------------------------ #
    # Violência contra criança / adolescente                              #
    # ------------------------------------------------------------------ #
    "child_specific": {
        "weight": 2.7,
        "terms": [
            "maus-tratos infantis", "abuso infantil", "negligência infantil",
            "violência contra criança", "agressão a menor", "maltrato infantil",
            "síndrome do bebê sacudido", "trauma craniano não acidental em criança",
            "lesões não acidentais em menor", "negligência de cuidados básicos",
            "privação de alimentos", "falta de higiene", "abandono de incapaz",
        ],
    },
}


def get_lexicon() -> dict:
    """Retorna o léxico completo."""
    return VIOLENCE_LEXICON


def get_category_weights() -> dict:
    """Retorna os pesos por categoria."""
    return {cat: info["weight"] for cat, info in VIOLENCE_LEXICON.items()}
