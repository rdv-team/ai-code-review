from __future__ import annotations

from pathlib import Path
from typing import Protocol

from review_tasks.integrations.mcp_registry import IdeAdapterError


class IdeAdapter(Protocol):
    name: str

    def generate_files(
        self,
        reviews_root: Path,
        templates_dir: Path,
        repo_root: Path,
        *,
        task_dirs: tuple[Path, ...],
        mcp_enabled: bool = True,
    ) -> None:
        """Generate IDE-specific files for a review root."""
