"""Validation and task-local storage for per-run user instructions."""

from __future__ import annotations

from pathlib import Path

from review_tasks.infrastructure.text_files import write_text_lf

USER_INSTRUCTION_MAX_LENGTH = 2000
USER_INSTRUCTION_RELATIVE_PATH = Path("_review_info") / "user_instruction.md"


class UserInstructionError(ValueError):
    """Raised when an explicitly supplied user instruction is invalid."""


def validate_user_instruction(value: str | None) -> str | None:
    """Return a canonical valid instruction or ``None`` when omitted."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise UserInstructionError("Пользовательская инструкция должна быть строкой.")
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        raise UserInstructionError("Пользовательская инструкция не должна быть пустой.")
    if "\0" in normalized:
        raise UserInstructionError("Пользовательская инструкция не должна содержать NUL-символ.")
    if len(normalized) > USER_INSTRUCTION_MAX_LENGTH:
        raise UserInstructionError(
            f"Пользовательская инструкция не должна превышать {USER_INSTRUCTION_MAX_LENGTH} символов."
        )
    return normalized


def write_user_instruction(review_dir: Path, value: str | None) -> Path | None:
    """Write an already validated instruction without wrappers or a trailing LF."""
    if value is None:
        return None
    output = review_dir / USER_INSTRUCTION_RELATIVE_PATH
    write_text_lf(output, value)
    return output
