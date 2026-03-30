"""
api/deps.py
===========
Injeção de dependências compartilhadas (singletons) da API.
Centraliza a criação de ReviewQueue e FeedbackStore para evitar
múltiplas instâncias abrindo o mesmo arquivo.
"""

from functools import lru_cache

from hitl.queue import ReviewQueue
from hitl.feedback import FeedbackStore


@lru_cache(maxsize=1)
def get_queue() -> ReviewQueue:
    return ReviewQueue()


@lru_cache(maxsize=1)
def get_feedback_store() -> FeedbackStore:
    return FeedbackStore()
