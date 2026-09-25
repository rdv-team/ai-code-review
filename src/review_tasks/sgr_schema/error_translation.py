"""Перевод ``pydantic.ValidationError`` в ``ReviewYamlError`` с русскими сообщениями.

Контракт ``review-result-yaml`` (spec) требует, чтобы каждая диагностика
включала путь до неверного поля и человекочитаемое описание причины на
русском. Pydantic по умолчанию даёт английские сообщения, поэтому этот
модуль реализует слой перевода (см. Decision 5 в design.md).

``ReviewYamlError`` определён здесь, потому что ``error_translation``
импортируется ``review_yaml`` (где раньше располагался класс) — единый
источник истины для исключения находится в пакете ``sgr_schema``.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError


class ReviewYamlError(ValueError):
    """Ошибка валидации YAML-результата ревью.

    Подкласс ``ValueError`` сохраняет совместимость с историческими
    ``except (OSError, ReviewYamlError)`` в ``cli.py``.
    """


_VALUE_ERROR_PREFIX = "Value error, "


_REASON_TEMPLATES: dict[str, str] = {
    "missing": "отсутствует",
    "extra_forbidden": "не является допустимым полем",
    "string_type": "должно быть строкой",
    "int_type": "должно быть целым числом",
    "int_parsing": "должно быть целым числом",
    "bool_type": "должно быть логическим значением",
    "bool_parsing": "должно быть логическим значением",
    "list_type": "должно быть списком",
    "dict_type": "должно быть объектом",
    "model_type": "должно быть объектом",
    "float_type": "должно быть числом",
}


def _format_path(loc: tuple[Any, ...]) -> str:
    """Формирует читаемый путь поля из Pydantic loc.

    Целочисленные индексы преобразуются в 1-based нотацию ``[N]``
    (соответствует историческим сообщениям ``review_yaml.py``).
    """
    parts: list[str] = []
    for token in loc:
        if isinstance(token, bool):
            parts.append(str(token))
        elif isinstance(token, int):
            parts.append(f"[{token + 1}]")
        else:
            parts.append(str(token))
    if not parts:
        return ""
    return ".".join(parts).replace(".[", "[")


def _render_reason(err: dict[str, Any]) -> str:
    """Преобразует одну ошибку Pydantic в русскую формулировку причины."""
    err_type = err.get("type", "")

    if err_type == "literal_error":
        ctx = err.get("ctx") or {}
        expected = ctx.get("expected", "")
        received = err.get("input")
        if received is not None:
            return f"должно быть одним из: {expected}. Получено: `{received}`"
        return f"должно быть одним из: {expected}"

    if err_type == "string_too_short":
        ctx = err.get("ctx") or {}
        min_length = ctx.get("min_length", 1)
        if min_length == 1:
            return "должно быть непустой строкой"
        return f"должно содержать не менее {min_length} символов"

    if err_type == "string_too_long":
        ctx = err.get("ctx") or {}
        max_length = ctx.get("max_length")
        if max_length is not None:
            return f"должно содержать не более {max_length} символов"
        return "слишком длинная строка"

    if err_type in {"greater_than_equal", "greater_than"}:
        ctx = err.get("ctx") or {}
        threshold = ctx.get("ge", ctx.get("gt"))
        operator = ">" if err_type == "greater_than" else ">="
        if threshold is not None:
            return f"должно быть {operator} {threshold}"
        return "значение слишком мало"

    if err_type in {"less_than_equal", "less_than"}:
        ctx = err.get("ctx") or {}
        threshold = ctx.get("le", ctx.get("lt"))
        operator = "<" if err_type == "less_than" else "<="
        if threshold is not None:
            return f"должно быть {operator} {threshold}"
        return "значение слишком велико"

    if err_type == "value_error":
        ctx = err.get("ctx") or {}
        error = ctx.get("error")
        if error is not None:
            text = str(error)
            if text:
                return text
        msg = err.get("msg", "")
        if msg.startswith(_VALUE_ERROR_PREFIX):
            return msg[len(_VALUE_ERROR_PREFIX):]
        return msg or "ошибка валидации"

    template = _REASON_TEMPLATES.get(err_type)
    if template is not None:
        return template

    return err.get("msg", "ошибка валидации")


def _compose_message(*, source: str, path: str, reason: str) -> str:
    if path:
        text = f"{source}: поле `{path}` {reason}"
    else:
        text = f"{source}: {reason}"
    if not text.endswith((".", "!", "?")):
        text = text + "."
    return text


def translate_validation_error(
    exc: ValidationError,
    *,
    source: str,
) -> ReviewYamlError:
    """Преобразует все ошибки ``ValidationError`` в ``ReviewYamlError``."""
    errors = exc.errors()
    if not errors:
        return ReviewYamlError(f"{source}: YAML не прошёл валидацию.")
    messages = [
        _compose_message(
            source=source,
            path=_format_path(tuple(err.get("loc", ()))),
            reason=_render_reason(err),
        )
        for err in errors
    ]
    return ReviewYamlError("\n".join(messages))


__all__ = ["ReviewYamlError", "translate_validation_error"]
