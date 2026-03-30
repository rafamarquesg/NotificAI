"""
hitl/queue.py
=============
Fila de revisão Human-in-the-Loop — persistida em SQLite via arquivo JSON-Lines.

Optamos por JSON-Lines (`.jsonl`) em vez de SQLite para:
  - Zero dependência extra (sem SQLAlchemy)
  - Portabilidade máxima (Colab, servidor, edge)
  - Legibilidade direta do arquivo para debug

Para escalar para produção → substituir o backend mantendo a interface pública
(Repository Pattern).

Interface pública:
    queue = ReviewQueue()
    queue.push(review_task)
    task = queue.pop_next_pending()
    queue.update_status(task_id, ValidationDecision)
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional

from .models import FeedbackRecord, ReviewStatus, ReviewTask, ValidationDecision

_DEFAULT_QUEUE_PATH = Path(__file__).parent.parent / "data" / "review_queue.jsonl"
_DEFAULT_FEEDBACK_PATH = Path(__file__).parent.parent / "data" / "feedback.jsonl"


class ReviewQueue:
    """
    Repositório da fila de revisão.
    Thread-safe via lock interno.
    """

    def __init__(self, queue_path: Optional[Path] = None):
        self._path = Path(queue_path or _DEFAULT_QUEUE_PATH)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def push(self, task: ReviewTask) -> None:
        """Adiciona uma nova tarefa à fila."""
        with self._lock:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(task.to_dict(), ensure_ascii=False) + "\n")

    def update(self, task_id: str, decision: ValidationDecision) -> bool:
        """
        Aplica a decisão do técnico a uma tarefa existente.
        Reescreve o arquivo (adequado para volumes <100k registros).
        """
        tasks = self._load_all()
        found = False

        for task in tasks:
            if task["task_id"] == task_id:
                task["status"] = decision.decision.value
                task["reviewed_at"] = decision.timestamp
                task["reviewer_id"] = decision.reviewer_id
                task["reviewer_notes"] = decision.notes
                if decision.agravo_confirmed:
                    task["agravo_confirmed"] = decision.agravo_confirmed.value
                found = True
                break

        if found:
            self._save_all(tasks)
        return found

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def get_pending(self, limit: int = 20) -> List[dict]:
        """Retorna tarefas pendentes ordenadas por score (maior primeiro)."""
        tasks = self._load_all()
        pending = [t for t in tasks if t["status"] == ReviewStatus.PENDING.value]
        pending.sort(key=lambda t: t.get("severity_score", 0), reverse=True)
        return pending[:limit]

    def get_by_id(self, task_id: str) -> Optional[dict]:
        for task in self._load_all():
            if task["task_id"] == task_id:
                return task
        return None

    def get_stats(self) -> dict:
        tasks = self._load_all()
        from collections import Counter
        counts = Counter(t["status"] for t in tasks)
        return {
            "total": len(tasks),
            "pending": counts.get(ReviewStatus.PENDING.value, 0),
            "approved": counts.get(ReviewStatus.APPROVED.value, 0),
            "rejected": counts.get(ReviewStatus.REJECTED.value, 0),
            "deferred": counts.get(ReviewStatus.DEFERRED.value, 0),
        }

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _load_all(self) -> List[dict]:
        if not self._path.exists():
            return []
        with self._lock:
            tasks = []
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            tasks.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return tasks

    def _save_all(self, tasks: List[dict]) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            for task in tasks:
                f.write(json.dumps(task, ensure_ascii=False) + "\n")
