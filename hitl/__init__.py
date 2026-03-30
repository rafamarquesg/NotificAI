"""Camada Human-in-the-Loop — NotificAI."""

from .models import (
    ReviewTask, ValidationDecision, FeedbackRecord,
    DetectionHighlight, ReviewStatus, AgravoType,
)
from .queue import ReviewQueue
from .feedback import FeedbackStore

__all__ = [
    "ReviewTask", "ValidationDecision", "FeedbackRecord",
    "DetectionHighlight", "ReviewStatus", "AgravoType",
    "ReviewQueue", "FeedbackStore",
]
