from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from review_tasks.infrastructure.text_files import read_text_required, write_text_lf
from review_tasks.integrations.mcp_registry import IdeAdapterError, codex_mcp_entry, load_mcp_registry

_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


class CodexAdapter:
    name = "codex"

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

        if mcp_enabled:
            for task_dir in task_dirs:
                merge_mcp_config(task_dir / ".codex" / "config.toml", registry_path)


def merge_mcp_config(config_path: Path, registry_path: Path) -> None:
    registry_servers = load_mcp_registry(registry_path)
    config = _load_toml_config(config_path)
    mcp_servers = config.setdefault("mcp_servers", {})
    if not isinstance(mcp_servers, dict):
        raise IdeAdapterError(f"Некорректный Codex config.toml: ключ mcp_servers должен быть таблицей ({config_path})")

    servers_by_url: dict[str, dict[str, Any]] = {}
    for server_id, server_config in mcp_servers.items():
        if not isinstance(server_config, dict):
            raise IdeAdapterError(
                f"Некорректный Codex config.toml: mcp_servers.{server_id} должен быть таблицей ({config_path})"
            )
        url = server_config.get("url")
        if isinstance(url, str):
            servers_by_url.setdefault(url.strip(), server_config)

    for registry_server in registry_servers:
        normalized_url = registry_server.url.strip()
        projected = codex_mcp_entry(registry_server)
        existing = servers_by_url.get(normalized_url)
        if existing is not None:
            _apply_codex_mcp_entry(existing, projected)
            continue

        mcp_servers[registry_server.server_id] = projected
        servers_by_url[normalized_url] = mcp_servers[registry_server.server_id]

    write_text_lf(config_path, _dump_toml(config))


def _apply_codex_mcp_entry(target: dict[str, Any], projected: dict[str, Any]) -> None:
    target["enabled"] = projected["enabled"]
    target["url"] = projected["url"]
    if "bearer_token_env_var" in projected:
        target["bearer_token_env_var"] = projected["bearer_token_env_var"]
    else:
        target.pop("bearer_token_env_var", None)

    projected_headers = projected.get("http_headers")
    if projected_headers is not None and not isinstance(projected_headers, dict):
        raise IdeAdapterError("Некорректный Codex config.toml: http_headers должен быть таблицей")

    http_headers = target.get("http_headers")
    if not isinstance(http_headers, dict):
        http_headers = {}
    else:
        http_headers = dict(http_headers)

    http_headers.pop("Authorization", None)
    if isinstance(projected_headers, dict):
        http_headers.update(projected_headers)

    if http_headers:
        target["http_headers"] = http_headers
    else:
        target.pop("http_headers", None)


def _load_toml_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        parsed = tomllib.loads(read_text_required(config_path))
    except tomllib.TOMLDecodeError as exc:
        raise IdeAdapterError(f"Некорректный TOML в {config_path}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise IdeAdapterError(f"Некорректный Codex config.toml: корень должен быть таблицей ({config_path})")
    return parsed


def _dump_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    scalar_items = [(key, value) for key, value in sorted(data.items()) if not isinstance(value, dict)]
    table_items = [(key, value) for key, value in sorted(data.items()) if isinstance(value, dict)]

    for key, value in scalar_items:
        lines.append(f"{_format_key(key)} = {_format_toml_value(value)}")
    if scalar_items and table_items:
        lines.append("")

    for key, value in table_items:
        _emit_toml_table(lines, [key], value)

    return "\n".join(lines).rstrip() + "\n"


def _emit_toml_table(lines: list[str], path: list[str], table: dict[str, Any]) -> None:
    scalar_items = [(key, value) for key, value in sorted(table.items()) if not isinstance(value, dict)]
    table_items = [(key, value) for key, value in sorted(table.items()) if isinstance(value, dict)]

    if scalar_items:
        lines.append(f"[{_format_table_path(path)}]")
        for key, value in scalar_items:
            lines.append(f"{_format_key(key)} = {_format_toml_value(value)}")
        lines.append("")

    for key, value in table_items:
        _emit_toml_table(lines, [*path, key], value)


def _format_table_path(path: list[str]) -> str:
    return ".".join(_format_key(part) for part in path)


def _format_key(key: str) -> str:
    if _BARE_KEY_RE.fullmatch(key):
        return key
    return _format_string(key)


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _format_string(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list):
        return f"[{', '.join(_format_toml_value(item) for item in value)}]"
    raise IdeAdapterError(f"Неподдерживаемый тип значения для записи TOML: {type(value).__name__}")


def _format_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
