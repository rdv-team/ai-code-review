from __future__ import annotations

import logging
import logging.handlers
import shlex
import sys
from pathlib import Path

from .contracts import now_iso

SERVICE_LOGGER_NAME = "review_tasks.local_service.events"

_service_logger: logging.Logger | None = None


class _ServiceEventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


def setup_service_logging(log_file: Path) -> logging.Logger:
    global _service_logger
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(SERVICE_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    formatter = _ServiceEventFormatter()

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    _service_logger = logger
    return logger


def get_service_logger() -> logging.Logger | None:
    return _service_logger


def shutdown_service_logging() -> None:
    global _service_logger
    logger = logging.getLogger(SERVICE_LOGGER_NAME)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    _service_logger = None


def _format_argv(argv: list[str]) -> str:
    return shlex.join(str(part) for part in argv)


def _log_event(event: str, message: str) -> None:
    logger = get_service_logger()
    if logger is None:
        return
    logger.info(f"{now_iso()} [{event}] {message}")


def log_init_start(issue_key: str, argv: list[str]) -> None:
    _log_event("INIT_START", f'task={issue_key} argv="{_format_argv(argv)}"')


def log_init_end(issue_key: str, exit_code: int, outcome: str) -> None:
    _log_event("INIT_END", f"task={issue_key} exit_code={exit_code} outcome={outcome}")


def log_agent_start(issue_key: str, ide: str, argv: list[str]) -> None:
    _log_event("AGENT_START", f'task={issue_key} ide={ide} argv="{_format_argv(argv)}"')


def log_agent_end(issue_key: str, ide: str, exit_code: int, outcome: str) -> None:
    _log_event("AGENT_END", f"task={issue_key} ide={ide} exit_code={exit_code} outcome={outcome}")


def log_error(issue_key: str, message: str) -> None:
    _log_event("ERROR", f"task={issue_key} {message}")


def log_config_reload(message: str) -> None:
    _log_event("CONFIG_RELOAD", f"service {message}")
