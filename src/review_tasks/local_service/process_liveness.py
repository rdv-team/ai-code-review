from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

from .contracts import parse_iso

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# FILETIME counts 100-nanosecond intervals since 1601-01-01; this is the offset
# in seconds between that epoch and the Unix epoch (1970-01-01).
_FILETIME_EPOCH_OFFSET_SEC = 11644473600.0
_DEFAULT_START_IDENTITY_TOLERANCE_SEC = 120.0
_WIN_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def pid_exists(pid: int) -> tuple[bool, str]:
    """Return whether an OS process with ``pid`` appears to exist."""
    if pid <= 0:
        return False, "invalid pid"
    if sys.platform.startswith("win"):
        return _pid_exists_windows(pid)
    return _pid_exists_posix(pid)


def _pid_exists_posix(pid: int) -> tuple[bool, str]:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False, "process not found (ESRCH)"
    except PermissionError:
        return True, "process exists (permission denied on signal 0)"
    except OSError as exc:
        return False, f"os.kill failed: {exc}"
    return True, "process exists (signal 0 succeeded)"


def _pid_exists_windows(pid: int) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_CREATE_NO_WINDOW,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"tasklist failed: {exc}"
    output = result.stdout.strip()
    lowered = output.lower()
    if not output or "no tasks" in lowered or "info:" in lowered:
        return False, "tasklist reports no matching process"
    if str(pid) not in output:
        return False, "tasklist output did not confirm pid"
    return True, "tasklist reports process running"


def get_process_create_time(pid: int) -> float | None:
    """Return the process creation time as Unix epoch seconds, or ``None``.

    OS-specific. Returns ``None`` on any failure or unsupported platform so that
    callers can degrade gracefully (the value is only used to corroborate PID
    identity, never as a liveness signal on its own).
    """
    if pid <= 0:
        return None
    if sys.platform.startswith("win"):
        return _get_process_create_time_windows(pid)
    if sys.platform.startswith("linux"):
        return _get_process_create_time_linux(pid)
    return None


def _get_process_create_time_windows(pid: int) -> float | None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(_WIN_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        ok = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
        if not ok:
            return None
        filetime = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        if filetime <= 0:
            return None
        return filetime / 1e7 - _FILETIME_EPOCH_OFFSET_SEC
    finally:
        kernel32.CloseHandle(handle)


def _get_process_create_time_linux(pid: int) -> float | None:
    try:
        raw = _read_proc_pid_stat(pid)
        starttime_ticks = _parse_proc_stat_starttime(raw)
        if starttime_ticks is None:
            return None
        boot_time = _read_proc_boot_time()
        if boot_time is None:
            return None
        clock_ticks = os.sysconf("SC_CLK_TCK")
        if clock_ticks <= 0:
            return None
    except (OSError, ValueError):
        return None
    return boot_time + starttime_ticks / clock_ticks


def _read_proc_pid_stat(pid: int) -> str:
    with open(f"/proc/{pid}/stat", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _parse_proc_stat_starttime(raw: str) -> int | None:
    # The comm field (field 2) is wrapped in parentheses and may itself contain
    # spaces or parentheses, so split on the final ')'. After it, fields start at
    # the state field (field 3); starttime is field 22 → index 19.
    close_index = raw.rfind(")")
    if close_index == -1:
        return None
    fields = raw[close_index + 1 :].split()
    if len(fields) < 20:
        return None
    try:
        return int(fields[19])
    except ValueError:
        return None


def _read_proc_boot_time() -> float | None:
    with open("/proc/stat", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("btime "):
                parts = line.split()
                if len(parts) >= 2:
                    return float(parts[1])
    return None


def start_identity_matches(
    recorded_started_at_iso: str,
    process_create_epoch: float,
    *,
    tolerance_sec: float = _DEFAULT_START_IDENTITY_TOLERANCE_SEC,
) -> bool:
    """Pure comparison: does the recorded start time match the process create time?

    ``pid.json`` is written a few seconds after the process actually starts, so a
    generous tolerance is applied. Returns ``False`` if the recorded timestamp is
    unparseable.
    """
    recorded = parse_iso(recorded_started_at_iso)
    if recorded is None:
        return False
    return abs(process_create_epoch - recorded.timestamp()) <= tolerance_sec


def check_review_process_liveness(pid_data: dict[str, Any]) -> tuple[bool, str]:
    """Check whether a persisted review process identity appears alive.

    Strictness (fail-safe toward *not alive*) and PID-reuse protection:

    - ``launcherPid`` must be a positive integer and the pid must exist in the OS.
    - When the OS exposes the process creation time (Windows ``GetProcessTimes``,
      Linux ``/proc/<pid>/stat``) **and** ``startedAt`` parses, the two are
      compared via :func:`start_identity_matches`. A mismatch is treated as PID
      reuse → not alive. This is the primary guard against false positives.
    - When the creation time is unavailable (unsupported platform / permission /
      error) or ``startedAt`` does not parse, the check degrades to the weaker
      rule "pid exists and ``startedAt`` is on record" and the returned reason
      states that start-time corroboration was unavailable.
    - When ``startedAt`` is absent entirely, pid existence alone is **not** enough
      and the process is considered not confirmed alive.
    - ``commandMarker`` is persisted for diagnostics only and is not verified
      against the running process.

    Returns ``(True, reason)`` only when life is confirmed; otherwise
    ``(False, reason)`` so callers can mark jobs ``interrupted``.
    """
    launcher_pid = pid_data.get("launcherPid")
    if not isinstance(launcher_pid, int) or isinstance(launcher_pid, bool) or launcher_pid <= 0:
        return False, "missing or invalid launcherPid"

    started_at = pid_data.get("startedAt")
    if not isinstance(started_at, str) or not started_at.strip():
        exists, exist_reason = pid_exists(launcher_pid)
        if exists:
            return False, "pid exists but startedAt missing; cannot confirm process identity"
        return False, f"process not alive: {exist_reason}"

    exists, exist_reason = pid_exists(launcher_pid)
    if not exists:
        return False, f"process not alive: {exist_reason}"

    create_epoch = get_process_create_time(launcher_pid)
    recorded = parse_iso(started_at)
    if create_epoch is not None and recorded is not None:
        if start_identity_matches(started_at, create_epoch):
            return True, "pid exists and process start time matches recorded startedAt"
        return False, "pid reused: process start time does not match recorded startedAt"

    return True, "pid exists with startedAt on record (start-time corroboration unavailable)"
