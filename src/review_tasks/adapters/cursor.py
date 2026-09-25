from __future__ import annotations

import json
from pathlib import Path

from review_tasks.infrastructure.text_files import read_text_required, write_text_lf
from review_tasks.integrations.mcp_registry import cursor_mcp_entry, load_mcp_registry


_CURSOR_REVIEW_START_TASK_FRONTMATTER = (
    "---\n"
    "name: /review-start-task\n"
    "id: review-start-task\n"
    "category: Review\n"
    "description: Автономное ревью текущей подготовленной задачи\n"
    "---\n\n"
)


def _format_cursor_command(frontmatter: str, body: str) -> str:
    return f"{frontmatter}{body.rstrip()}\n"


def format_cursor_review_start_task_command(body: str) -> str:
    return _format_cursor_command(_CURSOR_REVIEW_START_TASK_FRONTMATTER, body)


class CursorAdapter:
    name = "cursor"

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
        task_command = format_cursor_review_start_task_command(read_text_required(task_command_src))
        cursor_mcp_config = format_cursor_mcp_config(registry_path) if mcp_enabled else None
        for task_dir in task_dirs:
            write_text_lf(task_dir / ".cursor" / "commands" / "review-start-task.md", task_command)
            if cursor_mcp_config is not None:
                write_text_lf(task_dir / ".cursor" / "mcp.json", cursor_mcp_config)


def format_cursor_mcp_config(registry_path: Path) -> str:
    mcp_servers = {
        server.server_id: cursor_mcp_entry(server)
        for server in load_mcp_registry(registry_path)
    }
    return json.dumps({"mcpServers": mcp_servers}, ensure_ascii=False, indent=2) + "\n"
