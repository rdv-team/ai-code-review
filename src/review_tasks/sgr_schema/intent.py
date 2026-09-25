"""Pydantic-модель этапа Intent (SGR-голова, фаза 1)."""

from __future__ import annotations

from review_tasks.sgr_schema.primitives import NonBlankStr, SgrBaseModel


class Intent(SgrBaseModel):
    """Этап Intent: краткое резюме сообщений коммитов."""

    commits_summary: NonBlankStr


__all__ = ["Intent"]
