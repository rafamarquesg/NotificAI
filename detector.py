"""
Detector de violência em textos médicos usando léxico hierárquico.
"""

import re
from typing import List, Dict, Any, Set, Tuple

try:
    from .lexicon import get_lexicon  # uso como pacote
except ImportError:
    from lexicon import get_lexicon  # uso direto / testes

# Termos de negação que precedem um achado e invalidam a detecção
_NEGATION_PATTERN = re.compile(
    r'\b(não|nao|jamais|nunca|nega|negou|descarta|descartado|afasta|afastado'
    r'|exclui|excluído|ausente|sem|inexistente|improvável|sem\s+evidências'
    r'|sem\s+indícios|sem\s+sinais)\b[^.!?]{0,100}$',
    re.IGNORECASE,
)


def _extract_context(text: str, start: int, end: int, window: int = 120) -> str:
    """Retorna o trecho de contexto em torno de uma detecção."""
    ctx_start = max(0, start - window)
    ctx_end = min(len(text), end + window)
    return text[ctx_start:ctx_end].strip()


def _extract_sentence(text: str, start: int, end: int) -> str:
    """Retorna a frase completa que contém a detecção."""
    sentence_start = max(0, text.rfind('\n', 0, start))
    for sep in ('.', '!', '?'):
        pos = text.rfind(sep, 0, start)
        sentence_start = max(sentence_start, pos)
    sentence_end = len(text)
    for sep in ('.', '!', '?', '\n'):
        pos = text.find(sep, end)
        if pos != -1:
            sentence_end = min(sentence_end, pos + 1)
    return text[sentence_start:sentence_end].strip()


def _is_negated(text: str, match_start: int) -> bool:
    """Verifica se o achado é precedido por uma expressão de negação."""
    before = text[max(0, match_start - 120):match_start]
    return bool(_NEGATION_PATTERN.search(before))


def _spans_overlap(span: Tuple[int, int], seen: Set[Tuple[int, int]]) -> bool:
    """Verifica se um span sobrepõe algum já registrado."""
    s, e = span
    return any(a < e and s < b for a, b in seen)


class ViolenceDetector:
    """Detecta termos de violência em textos médicos com suporte a contexto e negação."""

    def __init__(self, context_window: int = 120):
        self.lexicon = get_lexicon()
        self.context_window = context_window
        self._compiled = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Pré-compila padrões regex por categoria, priorizando termos mais longos."""
        compiled: Dict[str, Dict[str, Any]] = {}
        for category, info in self.lexicon.items():
            # Ordenar do mais longo para o mais curto evita que um termo curto
            # "consuma" parte de um termo mais específico e mais longo.
            terms = sorted(info["terms"], key=len, reverse=True)
            escaped = [re.escape(t) for t in terms]
            # \b funciona bem para termos com apenas letras; para termos com
            # espaços ou hífens usamos lookaround de não-palavra.
            pattern = re.compile(
                r'(?<!\w)(?:' + '|'.join(escaped) + r')(?!\w)',
                re.IGNORECASE,
            )
            compiled[category] = {
                "pattern": pattern,
                "weight": info["weight"],
            }
        return compiled

    def analyze(self, text: str) -> List[Dict[str, Any]]:
        """
        Analisa o texto em busca de indicadores de violência.

        Retorna lista de dicts com:
          - term            : termo encontrado (texto original)
          - category        : categoria do léxico
          - weight          : peso da categoria
          - position_start  : posição inicial no texto
          - position_end    : posição final no texto
          - context         : trecho de ±context_window caracteres ao redor
          - sentence        : frase completa que contém o termo
          - negated         : True se o achado parece estar negado
        """
        results: List[Dict[str, Any]] = []
        seen_spans: Set[Tuple[int, int]] = set()

        for category, data in self._compiled.items():
            for match in data["pattern"].finditer(text):
                span = (match.start(), match.end())

                # Descartar matches que sobrepõem spans já registrados
                if _spans_overlap(span, seen_spans):
                    continue

                seen_spans.add(span)
                negated = _is_negated(text, match.start())

                results.append({
                    "term": match.group(0),
                    "category": category,
                    "weight": data["weight"],
                    "position_start": match.start(),
                    "position_end": match.end(),
                    "context": _extract_context(
                        text, match.start(), match.end(), self.context_window
                    ),
                    "sentence": _extract_sentence(text, match.start(), match.end()),
                    "negated": negated,
                })

        # Ordenar por peso decrescente e, em caso de empate, por posição
        results.sort(key=lambda r: (-r["weight"], r["position_start"]))
        return results

    def score(self, text: str, include_negated: bool = False) -> float:
        """
        Retorna a pontuação agregada de violência para o texto.

        Por padrão, achados negados não contam para a pontuação.
        """
        detections = self.analyze(text)
        return sum(
            d["weight"]
            for d in detections
            if include_negated or not d["negated"]
        )
