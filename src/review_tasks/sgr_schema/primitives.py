"""Общие Annotated-типы и базовый класс для SGR-моделей.

Все SGR-модели наследуются от ``SgrBaseModel``: это обеспечивает
``extra="forbid"`` рекурсивно (Decision 14 в design.md) — любое неизвестное
поле в YAML отклоняется с ошибкой.

Strict-mode оставлен в pydantic-дефолте (lax): значения, уже типизированные
``PyYAML`` после ``yaml.safe_load``, обычно поступают в нужных Python-типах.
Для чувствительных bool-полей (см. ``finding.py``)
применяется ``StrictBool``, чтобы исключить YAML-coerce (``"true" → True``,
``yes → True``).
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class SgrBaseModel(BaseModel):
    """Базовый класс для всех SGR-моделей.

    Запрещает неизвестные поля (`extra="forbid"`); это материализует
    закрытый список ключей YAML-ответа в коде и предотвращает молчаливый
    дрейф схемы.
    """

    model_config = ConfigDict(extra="forbid")


def _validate_non_blank(value: Any) -> str:
    """Отклоняет строки, пустые после ``str.strip()``, и нестроковые значения.

    Соответствует историческому ``not isinstance(value, str) or not value.strip()``
    из ``_validate_*`` функций ``review_yaml.py``. Регистрируется как
    ``BeforeValidator``, чтобы перехватывать сырой YAML-input до того,
    как Pydantic попытается привести значение к ``str``.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("должно быть непустой строкой")
    return value


def _validate_review_source_path(value: Any) -> str:
    """Проверяет путь к видимому review-source.

    - значение — непустая строка после ``str.strip``;
    - суффикс ``.reduced.bsl`` отклоняется (это сокращённая копия,
      используемая только как контекстное приложение);
    - разрешён обычный ``.bsl`` либо report ``Template.xml`` внутри сегмента
      ``Reports`` на произвольной глубине.

    Возвращает значение без изменений; нормализация слэшей не выполняется,
    чтобы сохранить идентичность с историческим поведением.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("должно быть непустой строкой")
    normalized = value.replace("\\", "/")
    lowered = normalized.lower()
    if lowered.endswith(".reduced.bsl"):
        raise ValueError("не может ссылаться на `.reduced.bsl`")
    parts = normalized.split("/")
    is_template = (
        bool(parts)
        and parts[-1].lower() == "template.xml"
        and any(part.lower() == "reports" for part in parts[:-1])
    )
    if not lowered.endswith(".bsl") and not is_template:
        raise ValueError(
            "должен указывать `.bsl` или `Template.xml` внутри сегмента `Reports`"
        )
    return value


_CANDIDATE_NAME_PATTERN = re.compile(r"^candidate-[1-9][0-9]*$")


def _validate_candidate_name(value: Any) -> str:
    """Проверяет machine-owned идентификатор кандидата ``candidate-N``."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("должно быть непустым идентификатором кандидата `candidate-N`")
    if _CANDIDATE_NAME_PATTERN.fullmatch(value) is None:
        raise ValueError(
            "должно быть механическим идентификатором кандидата "
            "в формате `candidate-N` (`^candidate-[1-9][0-9]*$`)"
        )
    return value


ReviewSourcePath = Annotated[str, BeforeValidator(_validate_review_source_path)]
BslFilePath = ReviewSourcePath
NonEmptyStr = Annotated[str, Field(min_length=1)]
NonBlankStr = Annotated[str, BeforeValidator(_validate_non_blank)]
LineNumber = Annotated[int, Field(ge=1, strict=True)]
NonNegativeInt = Annotated[int, Field(ge=0, strict=True)]
PositiveInt = Annotated[int, Field(ge=1, strict=True)]
CandidateName = Annotated[str, BeforeValidator(_validate_candidate_name)]


__all__ = [
    "BslFilePath",
    "CandidateName",
    "LineNumber",
    "NonBlankStr",
    "NonEmptyStr",
    "NonNegativeInt",
    "PositiveInt",
    "ReviewSourcePath",
    "SgrBaseModel",
]
