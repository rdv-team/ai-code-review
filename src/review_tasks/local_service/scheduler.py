from __future__ import annotations

import queue
import threading
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .orchestrator import JobOrchestrator

_STOP = object()


class ReviewWorkerPool:
    """Bounded FIFO worker pool: at most ``max_workers`` jobs run concurrently."""

    def __init__(
        self,
        orchestrator: JobOrchestrator,
        max_workers: int,
        *,
        on_job_started: Callable[[str], None] | None = None,
        on_job_finished: Callable[[str], None] | None = None,
        on_job_skipped: Callable[[str], None] | None = None,
        should_run: Callable[[str], bool] | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._max_workers = max(1, max_workers)
        self._on_job_started = on_job_started
        self._on_job_finished = on_job_finished
        self._on_job_skipped = on_job_skipped
        self._should_run = should_run
        self._queue: queue.Queue[str | object] = queue.Queue()
        self._workers: list[threading.Thread] = []
        self._running_job_ids: set[str] = set()
        self._lock = threading.Lock()
        self._stopped = False
        self._accepting = True

    def start(self) -> None:
        for _ in range(self._max_workers):
            thread = threading.Thread(target=self._worker_loop, name="review-worker", daemon=True)
            thread.start()
            self._workers.append(thread)

    def enqueue(self, job_id: str) -> None:
        with self._lock:
            if self._stopped:
                return
        self._queue.put(job_id)

    def stop_accepting(self) -> None:
        with self._lock:
            self._accepting = False

    def resize(self, max_workers: int) -> None:
        """Adjust worker count without interrupting running jobs.

        Increasing spawns additional daemon workers. Decreasing sends ``_STOP``
        sentinels so excess idle workers exit after their current item; workers
        already running a job finish normally first.
        """
        target = max(1, max_workers)
        to_add = 0
        to_remove = 0
        with self._lock:
            if self._stopped:
                return
            current = len(self._workers)
            self._max_workers = target
            if target > current:
                to_add = target - current
            elif target < current:
                to_remove = current - target
            else:
                return
        if to_add:
            for _ in range(to_add):
                thread = threading.Thread(target=self._worker_loop, name="review-worker", daemon=True)
                thread.start()
                with self._lock:
                    self._workers.append(thread)
        if to_remove:
            for _ in range(to_remove):
                self._queue.put(_STOP)

    def running_job_ids(self) -> set[str]:
        with self._lock:
            return set(self._running_job_ids)

    def wait_for_idle(self, timeout_sec: float) -> bool:
        end = time.monotonic() + timeout_sec
        while time.monotonic() < end:
            with self._lock:
                if not self._running_job_ids:
                    return True
            time.sleep(0.2)
        with self._lock:
            return not self._running_job_ids

    def stop(self, *, wait_timeout_sec: float = 5.0) -> None:
        with self._lock:
            self._stopped = True
            worker_count = len(self._workers)
        for _ in range(worker_count):
            self._queue.put(_STOP)
        end = time.monotonic() + wait_timeout_sec
        for thread in self._workers:
            remaining = max(0.0, end - time.monotonic())
            thread.join(timeout=remaining)

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _STOP:
                    return
                self._process_item(str(item))
            finally:
                self._queue.task_done()

    def _process_item(self, job_id: str) -> None:
        is_reattach = self._orchestrator.should_reattach(job_id)
        if not is_reattach:
            with self._lock:
                accepting = self._accepting
            if not accepting:
                if self._on_job_skipped is not None:
                    self._on_job_skipped(job_id)
                return
            if self._should_run is not None and not self._should_run(job_id):
                return
        with self._lock:
            self._running_job_ids.add(job_id)
        if self._on_job_started is not None:
            self._on_job_started(job_id)
        try:
            if is_reattach:
                self._orchestrator.monitor_reattached_job(job_id)
            else:
                self._orchestrator.run_job(job_id)
        finally:
            with self._lock:
                self._running_job_ids.discard(job_id)
            if self._on_job_finished is not None:
                self._on_job_finished(job_id)
