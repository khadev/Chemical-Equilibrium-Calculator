"""
core/cea_worker.py
=====================
Background-thread execution of CEA runs.  Tkinter/customtkinter
widgets must only be touched from the main thread, so this worker
places results on a ``queue.Queue`` that :class:`MainWindow` polls via
``after()`` — never blocking the UI event loop.
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

from core.cea_executor import CEAExecutor
from core.exceptions import CEAError, ParseError
from models.cea_result import CEAResult
from models.formulation import Formulation

log = logging.getLogger(__name__)


class WorkerMessage:
    """A single message placed on the result queue by the worker thread."""

    def __init__(self, kind: str, payload: object) -> None:
        """
        Args:
            kind: One of ``"log"``, ``"result"``, ``"error"``.
            payload: ``str`` for log/error, :class:`CEAResult` for result.
        """
        self.kind = kind
        self.payload = payload


class CEAWorker:
    """
    Runs :meth:`CEAExecutor.run` on a background ``threading.Thread``
    and reports progress/results through a thread-safe queue.

    Usage:
        worker = CEAWorker(executor)
        worker.start(formulation)
        # In the Tk main loop:
        self.after(100, self._poll(worker))
    """

    def __init__(self, executor: CEAExecutor) -> None:
        self._executor = executor
        self.queue: "queue.Queue[WorkerMessage]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None

    def start(self, formulation: Formulation, mode: str = "auto") -> None:
        """Start the CEA run on a background thread.

        Args:
            formulation: Propellant formulation to evaluate.
            mode: Engine mode — ``"auto"``, ``"fallback"``, or
                ``"fcea2"``. See :meth:`CEAExecutor.run`.
        """
        self._thread = threading.Thread(
            target=self._run, args=(formulation, mode), daemon=True)
        self._thread.start()

    def _run(self, formulation: Formulation, mode: str = "auto") -> None:
        try:
            result = self._executor.run(
                formulation,
                log_callback=lambda msg: self.queue.put(
                    WorkerMessage("log", msg)),
                mode=mode)
            self.queue.put(WorkerMessage("result", result))
        except ParseError as exc:
            self.queue.put(WorkerMessage("error", str(exc)))
            failed = CEAResult(success=False, error_message=str(exc))
            self.queue.put(WorkerMessage("result", failed))
        except CEAError as exc:
            self.queue.put(WorkerMessage("error", str(exc)))
            failed = CEAResult(success=False, error_message=str(exc))
            self.queue.put(WorkerMessage("result", failed))
        except Exception as exc:  # noqa: BLE001 — surface unexpected errors
            log.exception("Unhandled error in CEAWorker thread")
            self.queue.put(WorkerMessage("error", str(exc)))
            failed = CEAResult(success=False, error_message=str(exc))
            self.queue.put(WorkerMessage("result", failed))

    def is_running(self) -> bool:
        """Return True if the background thread is still active."""
        return self._thread is not None and self._thread.is_alive()
