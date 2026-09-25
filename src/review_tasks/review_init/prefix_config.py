from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from review_tasks.infrastructure import git as gitproc


REPOSITORY_DISCOVERY_MAX_DEPTH = 3
DISCOVERY_SKIP_DIR_NAMES = frozenset({".git", "node_modules", ".venv", "venv", ".cache"})


class RepositoryDiscoveryError(ValueError):
    """Raised when a repository path or container root cannot be resolved."""


@dataclass(frozen=True)
class RepositoryExpansionEvent:
    container: Path
    repositories: tuple[Path, ...]


def get_config_path() -> Path:
    return Path.home() / ".review-tasks" / "prefix-config.json"


def load_prefix_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Предупреждение: Не удалось прочитать конфигурацию префиксов: {exc}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print("Предупреждение: Не удалось прочитать конфигурацию префиксов: корневой JSON не является объектом.", file=sys.stderr)
        return {}
    return data


def save_prefix_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    path.write_bytes(payload.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def split_repository_list(value: Any) -> list[str]:
    """Parse comma/newline separated repository list preserving order."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,\r\n]+", value)
    elif isinstance(value, (list, tuple)):
        parts = [str(item) for item in value if isinstance(item, str)]
    else:
        return []
    repositories: list[str] = []
    seen: set[str] = set()
    for part in parts:
        repo = part.strip()
        if not repo or repo in seen:
            continue
        repositories.append(repo)
        seen.add(repo)
    return repositories


def entry_repositories(entry: dict[str, Any]) -> list[str]:
    repositories = split_repository_list(entry.get("repositories"))
    if repositories:
        return repositories
    return split_repository_list(entry.get("repo"))


def repositories_to_cli_arg(repositories: list[str]) -> str:
    return ",".join(repositories)


def repositories_to_api_value(repositories: list[str]) -> str:
    return "\n".join(repositories)


def extract_prefix(task_id: str) -> str:
    return task_id.strip().split("-", 1)[0].upper()


def group_tasks_by_prefix(tasks: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    seen: set[str] = set()
    for raw_task in tasks.split(","):
        task = raw_task.strip()
        if not task or task in seen:
            continue
        seen.add(task)
        prefix = extract_prefix(task)
        grouped.setdefault(prefix, []).append(task)
    return grouped


def _normalized_path_key(path: Path) -> str:
    return str(path.resolve()).casefold()


def _git_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = gitproc.git_result(args, cwd=cwd)
    return subprocess.CompletedProcess(
        result.args,
        result.returncode,
        result.stdout.decode("utf-8", errors="replace"),
        result.stderr.decode("utf-8", errors="replace"),
    )


def is_git_repository(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    try:
        result = _git_command(["rev-parse", "--is-inside-work-tree"], cwd=path)
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def git_repository_toplevel(path: Path) -> Path:
    result = _git_command(["rev-parse", "--show-toplevel"], cwd=path)
    if result.returncode != 0:
        raise RepositoryDiscoveryError(f"Путь '{path}' не является git-репозиторием.")
    toplevel = result.stdout.strip()
    if not toplevel:
        raise RepositoryDiscoveryError(f"Путь '{path}' не является git-репозиторием.")
    return Path(toplevel)


def should_skip_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    if os.name == "nt":
        try:
            return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except OSError:
            return False
    return False


def discover_git_repositories(
    container: Path,
    *,
    max_depth: int = REPOSITORY_DISCOVERY_MAX_DEPTH,
) -> list[Path]:
    container = container.resolve()
    if not container.is_dir():
        raise RepositoryDiscoveryError(f"Каталог контейнера не существует: {container}")
    if is_git_repository(container):
        return [git_repository_toplevel(container)]

    found: dict[str, Path] = {}

    def walk(directory: Path, depth: int) -> None:
        if is_git_repository(directory):
            toplevel = git_repository_toplevel(directory)
            found[_normalized_path_key(toplevel)] = toplevel.resolve()
            return
        if depth >= max_depth:
            return
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        except OSError as exc:
            raise RepositoryDiscoveryError(f"Не удалось прочитать каталог: {directory}") from exc
        for child in children:
            if not child.is_dir():
                continue
            if child.name in DISCOVERY_SKIP_DIR_NAMES or should_skip_link(child):
                continue
            walk(child, depth + 1)

    walk(container, 0)
    return sorted(found.values(), key=lambda item: _normalized_path_key(item))


def resolve_repository_entry(
    path: Path,
    *,
    expansion_events: list[RepositoryExpansionEvent] | None = None,
) -> list[Path]:
    resolved = path.expanduser().resolve()

    if not resolved.exists():
        raise RepositoryDiscoveryError(f"Путь не существует: {resolved}")

    if not resolved.is_dir():
        raise RepositoryDiscoveryError(f"Путь не является каталогом или git-репозиторием: {resolved}")

    if is_git_repository(resolved):
        return [git_repository_toplevel(resolved)]

    repositories = discover_git_repositories(resolved)
    if not repositories:
        raise RepositoryDiscoveryError(
            f"В каталоге {resolved} не найдено git-репозиториев "
            f"(глубина поиска: {REPOSITORY_DISCOVERY_MAX_DEPTH})."
        )
    if expansion_events is not None:
        expansion_events.append(
            RepositoryExpansionEvent(container=resolved, repositories=tuple(repositories))
        )
    return repositories


def resolve_repository_entries(
    paths: list[str],
    *,
    invocation_cwd: Path | None = None,
    expansion_events: list[RepositoryExpansionEvent] | None = None,
) -> list[Path]:
    if not paths:
        return []

    cwd = (invocation_cwd or Path.cwd()).resolve()
    resolved_entries: list[Path] = []
    seen_toplevels: set[str] = set()

    for raw_path in paths:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = (cwd / candidate).resolve()
        else:
            candidate = candidate.resolve()

        for repository in resolve_repository_entry(candidate, expansion_events=expansion_events):
            key = _normalized_path_key(repository)
            if key in seen_toplevels:
                continue
            seen_toplevels.add(key)
            resolved_entries.append(repository.resolve())

    return resolved_entries


def format_expansion_event_log(event: RepositoryExpansionEvent) -> str:
    count = len(event.repositories)
    if count % 10 == 1 and count % 100 != 11:
        noun = "репозиторий"
    elif count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        noun = "репозитория"
    else:
        noun = "репозиториев"
    repo_list = ", ".join(str(repo) for repo in event.repositories)
    return f"Найдено {count} {noun} в {event.container}: {repo_list}"
