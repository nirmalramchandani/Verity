"""
pipeline/task_manager.py
========================
Background task manager that decouples pipeline processing from HTTP connections.

When a user starts an ingestion, the actual work runs in a background thread.
The SSE endpoint merely reads from the task's output buffer.  If the browser
closes, the background thread keeps running to completion.

Usage:
    task = TaskManager.start("ingest", run_ingest, args=(path,))
    # Later, from an SSE endpoint:
    for msg in task.stream():
        yield msg
"""

import threading
import time
import uuid
from collections import deque
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    COMPLETE = "complete"
    FAILED   = "failed"


class BackgroundTask:
    """Wraps a generator-based pipeline and runs it in a background thread."""

    def __init__(self, task_id: str, name: str, generator_fn, args=(), kwargs=None):
        self.task_id      = task_id
        self.name         = name
        self.status       = TaskStatus.PENDING
        self.progress     = 0
        self.error        = None
        self.started_at   = None
        self.finished_at  = None
        self._buffer      = deque(maxlen=500)   # rolling buffer of SSE messages
        self._done_event  = threading.Event()
        self._gen_fn      = generator_fn
        self._args        = args
        self._kwargs       = kwargs or {}
        self._thread      = None

    def start(self):
        """Prepare the task for execution."""
        self.status     = TaskStatus.RUNNING
        self.started_at = datetime.now().isoformat()

    def _run(self):
        """Execute the generator, buffering all yielded messages."""
        try:
            gen = self._gen_fn(*self._args, **self._kwargs)
            for message in gen:
                self._buffer.append(message)
                # Try to extract progress percentage from the message
                if '"progress":' in message:
                    try:
                        import json
                        data = json.loads(message.strip())
                        self.progress = data.get("progress", self.progress)
                    except (json.JSONDecodeError, ValueError):
                        pass
            self.status = TaskStatus.COMPLETE
            self.progress = 100
        except Exception as e:
            import traceback
            self.error  = f"{str(e)}\n{traceback.format_exc()}"
            self.status = TaskStatus.FAILED
            from pipeline.notifier import notify_error
            notify_error("Background Task Crash", e, context=f"Task: {self.name} ({self.task_id})")
        finally:
            self.finished_at = datetime.now().isoformat()
            self._done_event.set()

    def stream(self, poll_interval: float = 0.3):
        """
        Yield buffered messages as they appear.  Safe to call from an SSE endpoint.
        If the SSE connection drops, the background thread continues unaffected.
        """
        cursor = 0
        while True:
            # Yield any new messages since our cursor
            buf_list = list(self._buffer)
            while cursor < len(buf_list):
                yield buf_list[cursor]
                cursor += 1

            # If the task is finished and we've drained the buffer, stop
            if self._done_event.is_set() and cursor >= len(list(self._buffer)):
                break

            time.sleep(poll_interval)

    def to_dict(self):
        return {
            "task_id":     self.task_id,
            "name":        self.name,
            "status":      self.status.value,
            "progress":    self.progress,
            "error":       self.error,
            "started_at":  self.started_at,
            "finished_at": self.finished_at,
        }


class TaskManager:
    """Singleton registry of background tasks."""

    _tasks: dict[str, BackgroundTask] = {}
    _current: dict[str, str] = {}  # name → task_id (latest task per name)

    @classmethod
    def create_task(cls, name: str, generator_fn, args=(), kwargs=None) -> BackgroundTask:
        """Create a new background task."""
        task_id = uuid.uuid4().hex[:12]
        task = BackgroundTask(task_id, name, generator_fn, args, kwargs)
        cls._tasks[task_id] = task
        cls._current[name] = task_id
        return task

    @classmethod
    def get(cls, task_id: str) -> BackgroundTask | None:
        return cls._tasks.get(task_id)

    @classmethod
    def get_latest(cls, name: str) -> BackgroundTask | None:
        tid = cls._current.get(name)
        return cls._tasks.get(tid) if tid else None

    @classmethod
    def get_status(cls, task_id: str) -> dict | None:
        task = cls._tasks.get(task_id)
        return task.to_dict() if task else None

    @classmethod
    def cleanup_old(cls, max_tasks: int = 20):
        """Remove old completed tasks to prevent memory bloat."""
        if len(cls._tasks) <= max_tasks:
            return
        completed = [
            (tid, t) for tid, t in cls._tasks.items()
            if t.status in (TaskStatus.COMPLETE, TaskStatus.FAILED)
        ]
        completed.sort(key=lambda x: x[1].finished_at or "")
        while len(cls._tasks) > max_tasks and completed:
            tid, _ = completed.pop(0)
            del cls._tasks[tid]
