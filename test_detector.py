"""
Testes para o ViolenceDetector.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from detector import ViolenceDetector


@pytest.fixture
def detector():
    return ViolenceDetector()


# ---------------------------------------------------------------------------
# Detecção básica
# ---------------------------------------------------------------------------

def test_detects_medical_formal_term(detector):
    text = "Paciente apresenta trauma contundente na região frontal."
    results = detector.analyze(text)
    terms = [r["term"].lower() for r in results]
    assert any("trauma contundente" in t for t in terms)


def test_detects_legal_term(detector):
    text = "Foi registrado boletim de ocorrência por lesão corporal."
    results = detector.analyze(text)
    categories = [r["category"] for r in results]
    assert "legal_police" in categories


def test_detects_colloquial_term(detector):
    text = "A paciente relatou que o companheiro lhe deu uma surra."
    results = detector.analyze(text)
    terms = [r["term"].lower() for r in results]
    assert any("surra" in t for t in terms)


# ---------------------------------------------------------------------------
# Contexto e posição
# ---------------------------------------------------------------------------

def test_result_contains_position(detector):
    text = "Apresenta equimoses múltiplas no tronco."
    results = detector.analyze(text)
    assert results, "Nenhuma detecção retornada"
    first = results[0]
    assert "position_start" in first
    assert "position_end" in first
    assert first["position_start"] >= 0
    assert first["position_end"] > first["position_start"]


def test_result_contains_context(detector):
    text = "Paciente chega com hematoma periorbital bilateral e relata agressão física."
    results = detector.analyze(text)
    assert results
    assert all("context" in r for r in results)
    assert all(len(r["context"]) > 0 for r in results)


def test_result_contains_sentence(detector):
    text = "O exame evidenciou marcas de estrangulamento. Paciente está estável."
    results = detector.analyze(text)
    assert results
    assert all("sentence" in r for r in results)


# ---------------------------------------------------------------------------
# Negação
# ---------------------------------------------------------------------------

def test_negated_detection_is_flagged(detector):
    text = "Paciente nega violência doméstica ou qualquer forma de agressão."
    results = detector.analyze(text)
    # Pelo menos um resultado deve ser marcado como negado
    assert any(r["negated"] for r in results), (
        "Detecção negada não foi identificada"
    )


def test_non_negated_detection_is_not_flagged(detector):
    text = "Vítima de violência doméstica, apresenta lesões graves."
    results = detector.analyze(text)
    assert results
    # Nenhuma detecção deve ser marcada como negada neste contexto
    assert not all(r["negated"] for r in results), (
        "Detecção válida foi indevidamente marcada como negada"
    )


# ---------------------------------------------------------------------------
# Deduplicação e sobreposição
# ---------------------------------------------------------------------------

def test_no_overlapping_spans(detector):
    text = "Politraumatismo com fraturas múltiplas e hematomas múltiplos."
    results = detector.analyze(text)
    spans = [(r["position_start"], r["position_end"]) for r in results]
    for i, (s1, e1) in enumerate(spans):
        for j, (s2, e2) in enumerate(spans):
            if i != j:
                assert not (s1 < e2 and s2 < e1), (
                    f"Spans sobrepostos: ({s1},{e1}) e ({s2},{e2})"
                )


def test_term_not_duplicated(detector):
    text = "Paciente com hematoma subdural."
    results = detector.analyze(text)
    found_terms = [r["term"].lower() for r in results]
    assert len(found_terms) == len(set(found_terms)), "Termo duplicado na saída"


# ---------------------------------------------------------------------------
# Ordenação por peso
# ---------------------------------------------------------------------------

def test_results_sorted_by_weight_desc(detector):
    text = (
        "Vítima de violência doméstica com trauma cranioencefálico e hematoma subdural. "
        "Relata surra frequente do companheiro. Apresenta bateu na mulher."
    )
    results = detector.analyze(text)
    weights = [r["weight"] for r in results]
    assert weights == sorted(weights, reverse=True), (
        "Resultados não estão ordenados por peso decrescente"
    )


# ---------------------------------------------------------------------------
# Pontuação agregada
# ---------------------------------------------------------------------------

def test_score_positive_for_violent_text(detector):
    text = "Paciente vítima de espancamento com lesão corporal grave."
    assert detector.score(text) > 0


def test_score_zero_for_neutral_text(detector):
    text = "Paciente apresenta febre e tosse há 3 dias."
    assert detector.score(text) == 0


def test_score_excludes_negated_by_default(detector):
    text_affirm = "Paciente sofreu violência doméstica."
    text_negated = "Paciente nega violência doméstica."
    score_affirm = detector.score(text_affirm)
    score_negated = detector.score(text_negated)
    assert score_affirm >= score_negated, (
        "Score com negação não deveria ser maior que sem negação"
    )


def test_score_includes_negated_when_requested(detector):
    text = "Paciente nega violência doméstica."
    score_with = detector.score(text, include_negated=True)
    score_without = detector.score(text, include_negated=False)
    assert score_with >= score_without
