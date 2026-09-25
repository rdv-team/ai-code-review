"""Pydantic-модель этапа Standards (SGR-голова, фаза 5)."""

from __future__ import annotations

from pydantic import field_validator

from review_tasks.sgr_schema.primitives import NonBlankStr, SgrBaseModel


class ApplicableDevStandardEntry(SgrBaseModel):
    """Один применимый std/rdv идентификатор из dev-standart файла."""

    id: NonBlankStr
    title: NonBlankStr


class ApplicableDevStandartFile(SgrBaseModel):
    """Routing-файл dev-standarts и явный поднабор стандартов из него."""

    file: NonBlankStr
    standards: list[ApplicableDevStandardEntry]

    @field_validator("standards")
    @classmethod
    def _standards_non_empty(
        cls, value: list[ApplicableDevStandardEntry]
    ) -> list[ApplicableDevStandardEntry]:
        if not value:
            raise ValueError("`standards` должен содержать хотя бы один элемент")
        return value


class Standards(SgrBaseModel):
    """Этап Standards Check: применимые стандарты и индексы платформы.

    Поля списков допускают пустоту: модель ревью может явно зафиксировать,
    что ни один стандарт не применим (например, простая dictionary-правка).
    """

    applicable_dev_standarts: list[ApplicableDevStandartFile] | None = None
    applicable_platform_index_files: list[str] | None = None
    applicable_ssl_files: list[str] | None = None
    rationale: str | None = None


__all__ = [
    "ApplicableDevStandardEntry",
    "ApplicableDevStandartFile",
    "Standards",
]
