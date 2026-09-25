"""Initial lifecycle gate for a review task capsule."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from .inspection import Readiness, classify_readiness, inspect_task_capsule
from .metadata import read_meta_summary, set_completed


class TaskStartOutcome(str, Enum):
    READY = "ready"
    REPEAT_REVIEW_SKIPPED = "repeat_review_skipped"
    REVIEW_ROOT = "review_root"
    INCOMPLETE = "incomplete"
    NOT_PREPARED = "not_prepared"


def prepare_task_start(task_root: Path) -> TaskStartOutcome:
    """Validate one task start and handle the completed-task branch."""
    inspection = inspect_task_capsule(task_root)
    readiness = classify_readiness(task_root, inspection=inspection)
    if readiness is not Readiness.READY:
        return TaskStartOutcome(readiness.value)

    summary = read_meta_summary(task_root, inspection=inspection)
    if summary["status"] == "completed":
        set_completed(task_root, run_status="repeat_review_skipped")
        return TaskStartOutcome.REPEAT_REVIEW_SKIPPED
    return TaskStartOutcome.READY
