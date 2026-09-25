from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from review_tasks.infrastructure.text_files import read_text_required, write_text_lf
from review_tasks.integrations.mcp_registry import load_mcp_registry, opencode_mcp_entry

_OPENCODE_SCHEMA = "https://opencode.ai/config.json"
_OPENCODE_REVIEW_START_TASK_DESCRIPTION = "Автономное ревью текущей подготовленной задачи"


class OpenCodeAdapter:
    name = "opencode"

    def generate_files(
        self,
        reviews_root: Path,
        templates_dir: Path,
        repo_root: Path,
        *,
        task_dirs: tuple[Path, ...],
        mcp_enabled: bool = True,
    ) -> None:
        del repo_root
        registry_path = templates_dir / "task" / "mcp" / "registry.json"
        del reviews_root

        task_command_src = templates_dir / "task" / "commands" / "review-start-task.md"
        task_command = format_opencode_command(
            _OPENCODE_REVIEW_START_TASK_DESCRIPTION,
            read_text_required(task_command_src),
        )
        task_config = format_opencode_config(registry_path) if mcp_enabled else None
        for task_dir in task_dirs:
            write_text_lf(task_dir / ".opencode" / "commands" / "review-start-task.md", task_command)
            if task_config is not None:
                write_text_lf(task_dir / "opencode.json", task_config)


def format_opencode_command(description: str, body: str) -> str:
    return f"---\ndescription: {description}\n---\n\n{body.rstrip()}\n"


def format_opencode_config(registry_path: Path) -> str:
    config: dict[str, Any] = {
        "$schema": _OPENCODE_SCHEMA,
        "mcp": {
            server.server_id: opencode_mcp_entry(server)
            for server in load_mcp_registry(registry_path)
        },
    }
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"
