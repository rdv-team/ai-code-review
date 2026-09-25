"""Pydantic-модель этапа Hypothesis (SGR-голова, фаза 3)."""

from __future__ import annotations

from review_tasks.sgr_schema.enums import ChangeType
from review_tasks.sgr_schema.primitives import NonBlankStr, SgrBaseModel


class Hypothesis(SgrBaseModel):
    """Этап Hypothesis: сформированная гипотеза о намерении и природе изменений."""

    change_type: ChangeType
    business_goal_hypothesis: NonBlankStr


__all__ = ["Hypothesis"]
