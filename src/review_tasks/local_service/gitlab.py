from __future__ import annotations

import json
import os
import re
import ssl
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

@dataclass(frozen=True)
class GitLabInstance:
    id: str
    base_url: str
    api_base_url: str
    token_env: str
    host: str
    port: int

    def to_json(self) -> dict[str, str]:
        return {
            "id": self.id,
            "baseUrl": self.base_url,
            "apiBaseUrl": self.api_base_url,
            "tokenEnv": self.token_env,
        }


@dataclass(frozen=True)
class GitLabRemoteRef:
    instance_id: str
    host: str
    port: int | None
    project_path: str


@dataclass(frozen=True)
class GitLabMrRef:
    instance_id: str | None
    project_path: str
    mr_id: int


@dataclass(frozen=True)
class GitLabRemoteResolution:
    ref: GitLabRemoteRef | None
    reason: str | None = None
    params: dict[str, Any] | None = None


@dataclass(frozen=True)
class GitLabProjectKey:
    instance_id: str
    project_path: str


@dataclass(frozen=True)
class GitRemoteCommandOutput:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class GitRemoteLookupResult:
    remote_url: str
    resolution: GitLabRemoteResolution | None = None
    error: str | None = None


@dataclass(frozen=True)
class GitLabApiResult:
    ok: bool
    items: list[dict[str, Any]]
    warning: dict[str, Any] | None = None


_SCP_REMOTE_RE = re.compile(r"^(?P<user>[^@\s]+)@(?P<host>[^:\s]+):(?P<path>.+)$")
_MR_PATH_RE = re.compile(r"^/(.+)/-/merge_requests/([1-9]\d*)(?:/.*)?$")
_INSTANCE_ID_RE = re.compile(r"[^a-z0-9]+")


def normalize_gitlab_instances(value: Any) -> tuple[GitLabInstance, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise _api_error("invalid_service_config", "gitlabInstances must be an array.")
    instances: list[GitLabInstance] = []
    used_ids: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise _api_error("invalid_service_config", f"gitlabInstances[{index}] must be an object.")
        base_url = _normalize_url_field(item.get("baseUrl"), field=f"gitlabInstances[{index}].baseUrl")
        api_base_url = _normalize_url_field(item.get("apiBaseUrl"), field=f"gitlabInstances[{index}].apiBaseUrl")
        token_env = _normalize_token_env(item.get("tokenEnv"), field=f"gitlabInstances[{index}].tokenEnv")
        host, port = _host_port_from_url(base_url, field=f"gitlabInstances[{index}].baseUrl")
        raw_id = item.get("id")
        if raw_id is None or not str(raw_id).strip():
            instance_id = generate_gitlab_instance_id(base_url, used_ids)
        else:
            instance_id = _normalize_instance_id(str(raw_id), fallback=generate_gitlab_instance_id(base_url, used_ids))
            if instance_id in used_ids:
                instance_id = _unique_instance_id(instance_id, used_ids)
        used_ids.add(instance_id)
        instances.append(
            GitLabInstance(
                id=instance_id,
                base_url=base_url,
                api_base_url=api_base_url,
                token_env=token_env,
                host=host,
                port=port,
            )
        )
    return tuple(instances)


def gitlab_instances_to_json(instances: tuple[GitLabInstance, ...] | list[GitLabInstance]) -> list[dict[str, str]]:
    return [instance.to_json() for instance in instances]


def generate_gitlab_instance_id(base_url: str, used_ids: set[str] | None = None) -> str:
    parsed = urllib.parse.urlparse(base_url.strip())
    host = (parsed.hostname or base_url).lower()
    if host.startswith("www."):
        host = host[4:]
    generated = _normalize_instance_id(host, fallback="gitlab")
    return _unique_instance_id(generated, used_ids or set())


def _normalize_instance_id(value: str, *, fallback: str) -> str:
    cleaned = _INSTANCE_ID_RE.sub("-", value.strip().lower()).strip("-")
    return cleaned or fallback


def _unique_instance_id(base_id: str, used_ids: set[str]) -> str:
    if base_id not in used_ids:
        return base_id
    suffix = 2
    while f"{base_id}-{suffix}" in used_ids:
        suffix += 1
    return f"{base_id}-{suffix}"


def _normalize_url_field(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _api_error("invalid_service_config", f"{field} must be a non-empty URL.")
    text = value.strip().rstrip("/")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise _api_error("invalid_service_config", f"{field} must be an http(s) URL.")
    return text


def _normalize_token_env(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _api_error("invalid_service_config", f"{field} must be a non-empty string.")
    return value.strip()


def _host_port_from_url(value: str, *, field: str = "url") -> tuple[str, int]:
    parsed = urllib.parse.urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise _api_error("invalid_service_config", f"{field} must be an http(s) URL.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise _api_error("invalid_service_config", f"{field} contains invalid port.") from exc
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return parsed.hostname.lower(), port


def normalize_gitlab_project_path(value: str) -> str | None:
    path = str(value).strip().replace("\\", "/")
    if not path:
        return None

    scp_match = _SCP_REMOTE_RE.match(path)
    if scp_match:
        path = scp_match.group("path")
    else:
        parsed = urllib.parse.urlparse(path)
        if parsed.scheme in {"http", "https", "ssh", "git"}:
            path = parsed.path
        elif "://" in path or ":" in path.split("/", 1)[0]:
            return None

    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not path or "/-/" in f"/{path}/" or path.startswith("-/"):
        return None
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2 or any(part in {".", ".."} for part in parts):
        return None
    return "/".join(parts).lower()


def parse_gitlab_remote(url: str, instances: tuple[GitLabInstance, ...] | list[GitLabInstance]) -> GitLabRemoteResolution:
    raw = str(url).strip()
    if not raw:
        return GitLabRemoteResolution(None, reason="empty_remote")

    host: str | None = None
    port: int | None = None
    path: str | None = None

    scp_match = _SCP_REMOTE_RE.match(raw)
    if scp_match:
        host = scp_match.group("host").lower()
        port = None
        path = scp_match.group("path")
    else:
        parsed = urllib.parse.urlparse(raw)
        if parsed.scheme in {"http", "https", "ssh", "git"} and parsed.hostname:
            host = parsed.hostname.lower()
            try:
                parsed_port = parsed.port
            except ValueError:
                return GitLabRemoteResolution(None, reason="invalid_port", params={"remoteUrl": raw})
            if parsed.scheme in {"http", "https"}:
                port = parsed_port if parsed_port is not None else (443 if parsed.scheme == "https" else 80)
            else:
                port = parsed_port
            path = parsed.path
        else:
            return GitLabRemoteResolution(None, reason="not_gitlab_remote", params={"remoteUrl": raw})

    project_path = normalize_gitlab_project_path(path or "")
    if host is None or project_path is None:
        return GitLabRemoteResolution(None, reason="not_gitlab_remote", params={"remoteUrl": raw})

    matches = [instance for instance in instances if host == instance.host and (port is None or port == instance.port)]
    if not matches:
        return GitLabRemoteResolution(None, reason="unconfigured_instance", params={"remoteUrl": raw, "host": host})
    if len(matches) > 1:
        return GitLabRemoteResolution(None, reason="ambiguous_instance", params={"remoteUrl": raw, "host": host})
    instance = matches[0]
    return GitLabRemoteResolution(
        GitLabRemoteRef(
            instance_id=instance.id,
            host=host,
            port=port,
            project_path=project_path,
        )
    )


def sanitize_git_remote_url(value: str) -> str:
    """Remove credentials and URL suffixes before returning a remote to a client."""
    raw = str(value).strip()
    if not raw:
        return ""
    scp_match = _SCP_REMOTE_RE.match(raw)
    if scp_match:
        return f"{scp_match.group('host')}:{scp_match.group('path')}"
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme and parsed.hostname:
        host = parsed.hostname
        try:
            port = parsed.port
        except ValueError:
            return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, "", ""))
        netloc = host if port is None else f"{host}:{port}"
        return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    return raw.split("#", 1)[0].split("?", 1)[0]


def parse_gitlab_mr_url(
    value: str,
    instances: tuple[GitLabInstance, ...] | list[GitLabInstance] = (),
) -> GitLabMrRef | None:
    parsed = urllib.parse.urlparse(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    match = _MR_PATH_RE.match(parsed.path)
    if not match:
        return None
    project_path = normalize_gitlab_project_path(match.group(1))
    if project_path is None:
        return None
    instance_id: str | None = None
    if instances:
        try:
            port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        except ValueError:
            return None
        matched = [instance for instance in instances if parsed.hostname.lower() == instance.host and port == instance.port]
        if len(matched) != 1:
            return None
        instance_id = matched[0].id
    return GitLabMrRef(instance_id=instance_id, project_path=project_path, mr_id=int(match.group(2)))


def title_contains_issue_key(title: str, issue_key: str) -> bool:
    pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(issue_key.upper())}(?![A-Z0-9])", re.IGNORECASE)
    return bool(pattern.search(str(title or "")))


GitRemoteRunner = Callable[[list[str], int], GitRemoteCommandOutput]


def resolve_git_remote(
    repo_path: str | Path,
    remote: str,
    instances: tuple[GitLabInstance, ...] | list[GitLabInstance],
    *,
    git_bin: str = "git",
    timeout_sec: int = 30,
    runner: GitRemoteRunner | None = None,
) -> GitRemoteLookupResult:
    argv = [git_bin, "-C", str(repo_path), "remote", "get-url", remote]
    try:
        result = runner(argv, timeout_sec) if runner is not None else _run_git_remote(argv, timeout_sec)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return GitRemoteLookupResult(remote_url="", error=str(exc))
    if result.returncode != 0:
        return GitRemoteLookupResult(
            remote_url="",
            error=result.stderr.strip() or f"remote '{remote}' is not available",
        )
    remote_url = (result.stdout or "").splitlines()[0].strip() if result.stdout else ""
    return GitRemoteLookupResult(
        remote_url=remote_url,
        resolution=parse_gitlab_remote(remote_url, instances),
    )


def list_git_remotes(
    repo_path: str | Path,
    *,
    git_bin: str = "git",
    timeout_sec: int = 30,
    runner: GitRemoteRunner | None = None,
) -> tuple[list[str], str | None]:
    argv = [git_bin, "-C", str(repo_path), "remote"]
    try:
        result = runner(argv, timeout_sec) if runner is not None else _run_git_remote(argv, timeout_sec)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], str(exc)
    if result.returncode != 0:
        return [], result.stderr.strip() or "Unable to inspect repository remotes."
    return [item.strip() for item in result.stdout.splitlines() if item.strip()], None


def _run_git_remote(argv: list[str], timeout_sec: int) -> GitRemoteCommandOutput:
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        timeout=timeout_sec,
        check=False,
    )
    return GitRemoteCommandOutput(
        returncode=result.returncode,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )


def token_lookup(instances: tuple[GitLabInstance, ...], used_instance_ids: set[str]) -> tuple[dict[str, str], list[dict[str, str]]]:
    tokens: dict[str, str] = {}
    missing: list[dict[str, str]] = []
    for instance in instances:
        if instance.id not in used_instance_ids:
            continue
        token = os.environ.get(instance.token_env, "").strip()
        if token:
            tokens[instance.id] = token
        else:
            missing.append({"id": instance.id, "tokenEnv": instance.token_env})
    return tokens, missing


class GitLabApiClient:
    def __init__(self, *, timeout_sec: int = 15) -> None:
        self.timeout_sec = timeout_sec
        self._ssl_context = ssl.create_default_context()

    def fetch_project_merge_requests(
        self,
        *,
        instance: GitLabInstance,
        token: str,
        project_path: str,
        issue_key: str,
    ) -> GitLabApiResult:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            url = self._merge_requests_url(
                instance=instance,
                project_path=project_path,
                issue_key=issue_key,
                page=page,
            )
            request = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "PRIVATE-TOKEN": token,
                    "User-Agent": "review-tasks-local-service",
                },
                method="GET",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_sec, context=self._ssl_context) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    if not isinstance(payload, list):
                        return GitLabApiResult(
                            ok=False,
                            items=items,
                            warning=project_warning("project_generic", instance, project_path, message="Unexpected GitLab response."),
                        )
                    items.extend(item for item in payload if isinstance(item, dict))
                    next_page = response.headers.get("X-Next-Page", "").strip()
            except urllib.error.HTTPError as exc:
                return GitLabApiResult(False, items, self._http_warning(exc, instance, project_path))
            except TimeoutError:
                return GitLabApiResult(False, items, project_warning("project_timeout", instance, project_path))
            except (urllib.error.URLError, socket.timeout) as exc:
                reason = getattr(exc, "reason", exc)
                if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                    return GitLabApiResult(False, items, project_warning("project_timeout", instance, project_path))
                return GitLabApiResult(
                    False,
                    items,
                    {"code": "instance_unreachable", "params": {"instanceId": instance.id, "baseUrl": instance.base_url}},
                )
            except Exception as exc:
                return GitLabApiResult(
                    False,
                    items,
                    project_warning("project_generic", instance, project_path, message=str(exc)),
                )
            if not next_page:
                break
            try:
                page = int(next_page)
            except ValueError:
                break
        return GitLabApiResult(True, items, None)

    @staticmethod
    def _merge_requests_url(
        *,
        instance: GitLabInstance,
        project_path: str,
        issue_key: str,
        page: int,
    ) -> str:
        encoded_project = urllib.parse.quote(project_path, safe="")
        query = urllib.parse.urlencode(
            {
                "state": "opened",
                "search": issue_key,
                "in": "title",
                "view": "simple",
                "per_page": "100",
                "page": str(page),
            }
        )
        return f"{instance.api_base_url.rstrip('/')}/projects/{encoded_project}/merge_requests?{query}"

    @staticmethod
    def _http_warning(exc: urllib.error.HTTPError, instance: GitLabInstance, project_path: str) -> dict[str, Any]:
        if exc.code in {401, 403}:
            return project_warning("project_access_denied", instance, project_path)
        if exc.code == 404:
            return project_warning("project_not_found", instance, project_path)
        if exc.code == 429:
            return project_warning("project_rate_limited", instance, project_path)
        return project_warning("project_generic", instance, project_path, message=f"HTTP {exc.code}")


def project_warning(
    code: str,
    instance: GitLabInstance,
    project_path: str,
    *,
    message: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"instanceId": instance.id, "projectPath": project_path}
    if message is not None:
        params["message"] = message
    return {"code": code, "params": params}


def _api_error(code: str, message: str) -> Exception:
    from .contracts import ApiError

    return ApiError(code, message)
