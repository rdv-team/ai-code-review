from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from review_tasks.infrastructure.text_files import read_text_required


class IdeAdapterError(RuntimeError):
    """IDE adapter configuration or template error."""


@dataclass(frozen=True)
class BearerEnvToken:
    env_var: str


@dataclass(frozen=True)
class McpServerEntry:
    server_id: str
    url: str
    expected_tools: tuple[str, ...]
    headers: dict[str, str]
    connection_id: str | None = None


_ENV_PLACEHOLDER_RE = re.compile(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}")
_BEARER_ENV_RE = re.compile(r"^Bearer\s+\{env:([A-Za-z_][A-Za-z0-9_]*)\}$")
_SERVER_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def load_mcp_registry(path: Path) -> tuple[McpServerEntry, ...]:
    raw = _read_text_required(path)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IdeAdapterError(f"Некорректный JSON MCP registry {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise IdeAdapterError(f"MCP registry должен быть JSON-объектом: {path}")

    schema_version = payload.get("schemaVersion")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise IdeAdapterError(f"MCP registry должен содержать целочисленный schemaVersion: {path}")

    servers = payload.get("servers")
    if not isinstance(servers, dict):
        raise IdeAdapterError(f"MCP registry должен содержать объект servers: {path}")

    entries: list[McpServerEntry] = []
    for server_id, server_config in servers.items():
        if not isinstance(server_id, str) or _SERVER_ID_RE.fullmatch(server_id) is None:
            raise IdeAdapterError(f"Некорректный server id в MCP registry: {server_id!r}")
        if not isinstance(server_config, dict):
            raise IdeAdapterError(f"MCP registry entry {server_id} должен быть объектом")
        if "fallback" in server_config:
            raise IdeAdapterError(f"MCP registry entry {server_id} содержит запрещённое поле fallback")

        url = _required_non_empty_string(server_config, "url", server_id)
        expected_tools = server_config.get("expectedTools")
        if (
            not isinstance(expected_tools, list)
            or not expected_tools
            or any(not isinstance(tool, str) or not tool for tool in expected_tools)
        ):
            raise IdeAdapterError(f"MCP registry entry {server_id} должен содержать непустой список expectedTools")

        headers = _required_headers(server_config, server_id)

        connection_id_value = server_config.get("connection_id")
        connection_id: str | None = None
        if connection_id_value is not None:
            if not isinstance(connection_id_value, str) or not connection_id_value:
                raise IdeAdapterError(f"MCP registry entry {server_id} содержит некорректный connection_id")
            connection_id = connection_id_value

        entries.append(
            McpServerEntry(
                server_id=server_id,
                url=url,
                expected_tools=tuple(expected_tools),
                headers=headers,
                connection_id=connection_id,
            )
        )

    return tuple(entries)


def cursor_mcp_entry(server: McpServerEntry) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "url": _resolve_url_env(server.url, server.server_id),
        "headers": {
            name: _convert_cursor_env_placeholders(value)
            for name, value in server.headers.items()
        },
    }
    if server.connection_id is not None:
        entry["connection_id"] = server.connection_id
    return entry


def opencode_mcp_entry(server: McpServerEntry) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "remote",
        "url": _resolve_url_env(server.url, server.server_id),
        "enabled": True,
        "headers": dict(server.headers),
    }
    if is_bearer_authorization(server.headers.get("Authorization")):
        entry["oauth"] = False
    return entry


def codex_mcp_entry(server: McpServerEntry) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "enabled": True,
        "url": _resolve_url_env(server.url, server.server_id),
    }
    bearer_env = parse_bearer_env_token(server.headers.get("Authorization"))
    http_headers: dict[str, str] = {}
    for name, value in server.headers.items():
        if name == "Authorization" and bearer_env is not None:
            entry["bearer_token_env_var"] = bearer_env.env_var
            continue
        http_headers[name] = value
    if http_headers:
        entry["http_headers"] = http_headers
    return entry


def parse_bearer_env_token(value: str | None) -> BearerEnvToken | None:
    if value is None:
        return None
    match = _BEARER_ENV_RE.fullmatch(value)
    if match is None:
        return None
    return BearerEnvToken(env_var=match.group(1))


def mcp_bearer_env_var_names(servers: tuple[McpServerEntry, ...]) -> tuple[str, ...]:
    names = {
        token.env_var
        for server in servers
        if (token := parse_bearer_env_token(server.headers.get("Authorization"))) is not None
    }
    return tuple(sorted(names))


def mcp_url_env_var_names(servers: tuple[McpServerEntry, ...]) -> tuple[str, ...]:
    names: set[str] = set()
    for server in servers:
        for match in _ENV_PLACEHOLDER_RE.finditer(server.url):
            names.add(match.group(1))
    return tuple(sorted(names))


def is_bearer_authorization(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith("Bearer ")


def _resolve_url_env(url: str, server_id: str) -> str:
    def _resolve(match: re.Match[str]) -> str:
        var = match.group(1)
        value = os.environ.get(var, "").strip()
        if not value:
            raise IdeAdapterError(
                f"MCP server '{server_id}': env var '{var}' для url не задана или пуста"
            )
        return value

    return _ENV_PLACEHOLDER_RE.sub(_resolve, url)


def _convert_cursor_env_placeholders(value: str) -> str:
    return _ENV_PLACEHOLDER_RE.sub(lambda match: f"${{env:{match.group(1)}}}", value)


def _read_text_required(path: Path) -> str:
    if not path.is_file():
        raise IdeAdapterError(f"MCP registry не найден: {path}")
    return read_text_required(path)


def _required_non_empty_string(data: dict[object, object], key: str, server_id: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise IdeAdapterError(f"MCP registry entry {server_id} должен содержать непустой {key}")
    return value


def _required_headers(data: dict[object, object], server_id: str) -> dict[str, str]:
    value = data.get("headers")
    if not isinstance(value, dict):
        raise IdeAdapterError(f"MCP registry entry {server_id} должен содержать объект headers")
    headers: dict[str, str] = {}
    for name, header_value in value.items():
        if not isinstance(name, str) or not name:
            raise IdeAdapterError(f"MCP registry entry {server_id} содержит некорректное имя header")
        if not isinstance(header_value, str):
            raise IdeAdapterError(f"MCP registry entry {server_id} содержит нестроковое значение header {name}")
        headers[name] = header_value
    return headers
