"""Layout inspection and readiness classification for a review task capsule."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


REVIEW_INFO_DIR = Path("_review_info")
AGENTS_FILE = Path("AGENTS.md")
META_FILE = REVIEW_INFO_DIR / "meta.txt"
STAGED_TASK_FILES = (
    REVIEW_INFO_DIR / "review_prompt_stage1.md",
    REVIEW_INFO_DIR / "review_prompt_stage2.md",
    REVIEW_INFO_DIR / "review_bsl.md",
)
REQUIRED_TASK_FILES = (AGENTS_FILE, META_FILE, *STAGED_TASK_FILES)

LEGACY_SINGLE_PROMPT = "review_prompt.md"
INDEXED_PROMPT_RE = re.compile(r"^review_prompt_\d{3}\.md$")
INDEXED_BSL_RE = re.compile(r"^review_bsl_\d{3}\.md$")
REVIEW_ARTIFACT_NAMES = frozenset(
    {
        LEGACY_SINGLE_PROMPT,
        *(path.name for path in STAGED_TASK_FILES),
    }
)


class Readiness(str, Enum):
    READY = "ready"
    REVIEW_ROOT = "review_root"
    INCOMPLETE = "incomplete"
    NOT_PREPARED = "not_prepared"


@dataclass(frozen=True)
class TaskCapsuleInspection:
    missing_required_files: tuple[Path, ...]
    legacy_artifacts: tuple[Path, ...]
    has_review_artifacts: bool

    @property
    def has_canonical_staged_layout(self) -> bool:
        return not self.legacy_artifacts and not any(
            path in STAGED_TASK_FILES for path in self.missing_required_files
        )

    @property
    def is_ready(self) -> bool:
        return not self.missing_required_files and not self.legacy_artifacts


def _review_info_entry_names(review_info: Path) -> tuple[str, ...]:
    try:
        return tuple(sorted(path.name for path in review_info.iterdir()))
    except OSError:
        return ()


def _is_legacy_artifact(name: str) -> bool:
    return (
        name == LEGACY_SINGLE_PROMPT
        or INDEXED_PROMPT_RE.fullmatch(name) is not None
        or INDEXED_BSL_RE.fullmatch(name) is not None
    )


def _is_review_artifact(name: str) -> bool:
    return name in REVIEW_ARTIFACT_NAMES or _is_legacy_artifact(name)


def inspect_task_capsule(task_root: Path) -> TaskCapsuleInspection:
    """Inspect the current task root once and return reusable layout facts."""
    missing_required_files = tuple(
        relative for relative in REQUIRED_TASK_FILES if not (task_root / relative).is_file()
    )
    entry_names = _review_info_entry_names(task_root / REVIEW_INFO_DIR)
    legacy_artifacts = tuple(
        REVIEW_INFO_DIR / name for name in entry_names if _is_legacy_artifact(name)
    )
    has_review_artifacts = (task_root / META_FILE).exists() or any(
        _is_review_artifact(name) for name in entry_names
    )
    return TaskCapsuleInspection(
        missing_required_files=missing_required_files,
        legacy_artifacts=legacy_artifacts,
        has_review_artifacts=has_review_artifacts,
    )


def _has_immediate_capsule_child(task_root: Path) -> bool:
    try:
        children = task_root.iterdir()
        return any(
            child.is_dir()
            and (child / AGENTS_FILE).is_file()
            and (child / META_FILE).is_file()
            for child in children
        )
    except OSError:
        return False


def classify_readiness(
    task_root: Path,
    *,
    inspection: TaskCapsuleInspection | None = None,
) -> Readiness:
    """Classify the invocation directory in the required deterministic order."""
    current = inspection if inspection is not None else inspect_task_capsule(task_root)
    if current.is_ready:
        return Readiness.READY
    if _has_immediate_capsule_child(task_root):
        return Readiness.REVIEW_ROOT
    if current.has_review_artifacts:
        return Readiness.INCOMPLETE
    return Readiness.NOT_PREPARED
