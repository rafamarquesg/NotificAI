"""
Monitor de pasta em tempo real usando watchdog.

Detecta novos PDFs adicionados a uma pasta monitorada e
os processa automaticamente via processor.process_file().
"""

import logging
import queue
import sqlite3
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


class _PDFHandler:
    """Adaptador de evento watchdog para processar novos PDFs."""

    def __init__(self, q: queue.Queue):
        self._queue = q

    def dispatch(self, event):
        path = None
        if isinstance(event, FileCreatedEvent):
            path = event.src_path
        elif isinstance(event, FileMovedEvent):
            path = event.dest_path
        if path and path.lower().endswith(".pdf"):
            self._queue.put(Path(path))


class FolderWatcher(threading.Thread):
    """
    Thread que monitora uma pasta e processa novos PDFs automaticamente.

    Uso:
        watcher = FolderWatcher(
            folder_path="/mnt/prontuarios",
            conn=conn,
            on_new_doc=lambda result: st.rerun(),
        )
        watcher.start()
        # ...
        watcher.stop()
        watcher.join(timeout=5)
    """

    def __init__(
        self,
        folder_path: str,
        conn: sqlite3.Connection,
        on_new_doc: Optional[Callable] = None,
    ):
        """
        Args:
            folder_path: pasta a monitorar.
            conn:        conexão SQLite para persistência.
            on_new_doc:  callback chamado após cada arquivo processado.
                         Recebe um ProcessingResult como argumento.
        """
        super().__init__(daemon=True, name="NotificAI-FolderWatcher")
        self.folder_path = Path(folder_path)
        self.conn = conn
        self.on_new_doc = on_new_doc
        self._stop_event = threading.Event()
        self._queue: queue.Queue = queue.Queue()
        self.processed: list = []
        self.errors: list = []

    def run(self):
        if not HAS_WATCHDOG:
            logger.warning("watchdog não instalado. Monitoramento de pasta desabilitado.")
            return

        if not self.folder_path.exists():
            logger.error("Pasta não encontrada: %s", self.folder_path)
            return

        handler = _FileEventHandler(self._queue)
        observer = Observer()
        observer.schedule(handler, str(self.folder_path), recursive=False)
        observer.start()
        logger.info("Monitorando pasta: %s", self.folder_path)

        try:
            while not self._stop_event.is_set():
                try:
                    pdf_path = self._queue.get(timeout=1.0)
                    self._process(pdf_path)
                except queue.Empty:
                    continue
        finally:
            observer.stop()
            observer.join()
            logger.info("Monitoramento encerrado.")

    def _process(self, pdf_path: Path):
        from core.processor import process_file
        try:
            file_bytes = pdf_path.read_bytes()
            result = process_file(
                self.conn,
                file_bytes,
                pdf_path.name,
                folder_path=str(self.folder_path),
            )
            self.processed.append(result)
            logger.info(
                "Processado: %s → %s (score=%.2f)",
                pdf_path.name,
                result.notification_type,
                result.score,
            )
            if self.on_new_doc:
                self.on_new_doc(result)
        except Exception as exc:
            logger.error("Erro ao processar %s: %s", pdf_path.name, exc)
            self.errors.append({"file": pdf_path.name, "error": str(exc)})

    def stop(self):
        self._stop_event.set()

    def scan_existing(self):
        """Processa PDFs que já existem na pasta ao iniciar o monitoramento."""
        for pdf_path in sorted(self.folder_path.glob("*.pdf")):
            self._process(pdf_path)


if HAS_WATCHDOG:
    class _FileEventHandler(FileSystemEventHandler):
        def __init__(self, q: queue.Queue):
            self._queue = q

        def on_created(self, event):
            if not event.is_directory and event.src_path.lower().endswith(".pdf"):
                self._queue.put(Path(event.src_path))

        def on_moved(self, event):
            if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
                self._queue.put(Path(event.dest_path))
