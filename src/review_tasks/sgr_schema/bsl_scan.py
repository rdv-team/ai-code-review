"""Pydantic-модель этапа BSL Scan (SGR-голова, фаза 2)."""

from __future__ import annotations

from pydantic import Field

from review_tasks.sgr_schema.primitives import NonBlankStr, SgrBaseModel


class BslScan(SgrBaseModel):
    """Этап BSL Scan: наблюдаемые артефакты изменений в BSL.

    ``observed_artifacts`` — короткий список фактов из дельты файлов
    (вызовы методов, имена реквизитов, сигнатуры процедур). Контракт
    ``review_yaml.py`` ограничивал длину 3..7 элементов; правило сохранено.
    """

    observed_artifacts: list[NonBlankStr] = Field(min_length=3, max_length=7)
    observed_change_signature: NonBlankStr


__all__ = ["BslScan"]
