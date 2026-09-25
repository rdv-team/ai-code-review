"""Pure helpers for safe GitLab source permalinks."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit


_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_SCP_REMOTE_RE = re.compile(
    r"^(?P<user>[^@\s/:]+)@(?P<host>[^\s/:]+):(?P<path>[^?#]+?)(?:[?#].*)?$"
)
_TARGET_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def is_git_commit_sha(value: str) -> bool:
    return isinstance(value, str) and _TARGET_RE.fullmatch(value) is not None


def normalize_source_path(value: str) -> str | None:
    """Normalize a repository-relative path without accepting traversal."""
    if not isinstance(value, str) or not value or _CONTROL_RE.search(value):
        return None
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith("/") or not normalized:
        return None
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)


def normalize_git_remote_project_url(remote_url: str) -> str | None:
    """Convert an unambiguous Git remote to a credential-free HTTP(S) URL."""
    if not isinstance(remote_url, str) or not remote_url or _CONTROL_RE.search(remote_url):
        return None
    raw = remote_url.strip()
    if not raw:
        return None

    scp_match = _SCP_REMOTE_RE.fullmatch(raw)
    if scp_match:
        host = scp_match.group("host").lower()
        path = scp_match.group("path")
        scheme = "https"
        port = None
    else:
        try:
            parsed = urlsplit(raw)
            port = parsed.port
        except ValueError:
            return None
        if parsed.scheme not in {"http", "https", "ssh"} or not parsed.hostname:
            return None
        if parsed.scheme == "ssh" and port not in {None, 22}:
            return None
        scheme = parsed.scheme if parsed.scheme in {"http", "https"} else "https"
        if parsed.scheme == "ssh":
            port = None
        host = parsed.hostname.lower()
        path = parsed.path

    path = unquote(path).strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    normalized_path = normalize_source_path(path)
    if normalized_path is None or len(normalized_path.split("/")) < 2:
        return None
    if any(part == "-" for part in normalized_path.split("/")):
        return None

    host_part = host
    if ":" in host and not host.startswith("["):
        host_part = f"[{host}]"
    if port is not None and scheme in {"http", "https"}:
        default_port = 443 if scheme == "https" else 80
        if port != default_port:
            host_part = f"{host_part}:{port}"
    encoded_path = quote(normalized_path, safe="/-._~")
    return urlunsplit((scheme, host_part, f"/{encoded_path}", "", ""))


def build_gitlab_blob_url(
    project_url: str,
    target: str,
    source_path: str,
    start_line: int,
    end_line: int,
) -> str | None:
    """Build a commit-specific GitLab blob URL with a line anchor."""
    canonical_project = normalize_git_remote_project_url(project_url)
    normalized_path = normalize_source_path(source_path)
    if (
        canonical_project is None
        or canonical_project != project_url.rstrip("/")
        or not is_git_commit_sha(target)
        or normalized_path is None
        or isinstance(start_line, bool)
        or isinstance(end_line, bool)
        or not isinstance(start_line, int)
        or not isinstance(end_line, int)
        or start_line < 1
        or end_line < start_line
    ):
        return None
    encoded_path = quote(normalized_path, safe="/-._~")
    anchor = f"#L{start_line}" if start_line == end_line else f"#L{start_line}-{end_line}"
    return f"{canonical_project}/-/blob/{target.lower()}/{encoded_path}{anchor}"


def resolve_git_remote_project_url(repo_root: Path, remote: str) -> str | None:
    """Resolve one configured remote locally; failures intentionally degrade to None."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", remote],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    lines = result.stdout.splitlines()
    if len(lines) != 1:
        return None
    return normalize_git_remote_project_url(lines[0])
