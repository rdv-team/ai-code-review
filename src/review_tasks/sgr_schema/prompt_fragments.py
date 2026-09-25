"""Markdown-фрагменты SGR-промпта, генерируемые из ``sgr_schema``.

Единственный writeable источник истины для повторяющихся фрагментов
staged-шаблонов ``review_prompt_stage1.md`` и ``review_prompt_stage2.md``:

- ``render_sgr_response_skeleton_body()`` — YAML-скелет тела ответа
  (``findings`` … ``missing_context``) для стадии 2.
- ``render_field_constraints_note()`` — прозовая сноска о nullable-полях
  под секцией «Формат ответа» стадии 2.

Все функции — чистые, без аргументов и побочных эффектов; повторный
вызов даёт побайтно идентичный результат. Используются модулем
``review_tasks.cli`` при рендере ``_review_info/review_prompt_stage*.md``.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import get_args

from review_tasks.sgr_schema.enums import (
    ConfidenceLevel,
    FalsePositiveRisk,
    FindingSource,
    FOCUS_AREA_CATALOG,
    SelfCheckDecision,
    Severity,
    TraceStatus,
    VerificationStatus,
    VerificationSummary,
)


def _join_args(alias: object) -> str:
    return " | ".join(get_args(alias))


@lru_cache(maxsize=1)
def render_focus_areas_list() -> str:
    """Нумерованный Markdown-список SGR-областей в порядке `FOCUS_AREA_CATALOG`.

    Формат строки: ``N. `<name>` — <description> Источник: <source_hint>.``
    Описание и source_hint берутся из ``FocusAreaMeta`` как есть; backticks
    вокруг path-глобов в ``source_hint`` объявлены прямо в каталоге.
    """
    lines: list[str] = []
    for ordinal, meta in enumerate(FOCUS_AREA_CATALOG, start=1):
        lines.append(
            f"{ordinal}. `{meta.name}` — {meta.description} "
            f"Источник: {meta.source_hint}."
        )
    return "\n".join(lines) + "\n"


# Шаблон YAML-скелета «Формат ответа».
#
# YAML-скелеты «Формат ответа»; union-перечисления заменены
# токенами ``{ENUM:<name>}``, раскрываемыми в ``_render_skeleton_yaml()``.
_RESPONSE_SKELETON_BODY_TEMPLATE = """\
findings:
  - name: candidate-1
    area: <one of 12>
    file: "..."
    start_line: 12
    end_line: 18
    observation: "..."
    source: {ENUM:finding_source}
    confidence: {ENUM:confidence}
    verification:                       # опционально
      needed: true | false
      channels:
        - capability: v8std-standards-diagnostics | ssl-library-search | platform-docs | bsl-syntax-check
          status: {ENUM:verification_status}
          result_note: "..."
      verification_summary: {ENUM:verification_summary}
    self_check:
      false_positive_risk: {ENUM:false_positive_risk}
      alternative_interpretation: "..." | null
      decision: {ENUM:self_check_decision}
      drop_reason: null
    traces:                             # обязательно; [] если нет межстрочной трассы
      - established_at: 12
        obligation: "строка A создаёт обязательство; строка B должна закрыть или нарушить его"
        satisfied_at: null
        status: {ENUM:trace_status}
    severity: {ENUM:severity_nullable}
    suggestion: "Конкретная рекомендация по исправлению; при возможности — BSL-сниппет"
  - name: candidate-2                    # отдельная запись для каждого candidate
    area: correctness
    file: "..."
    start_line: 20
    end_line: 24
    observation: "Рекурсивная проверка покрытия периода может пропустить разрыв между соседними спецификациями."
    source: {ENUM:finding_source}
    confidence: {ENUM:confidence}
    self_check:
      false_positive_risk: {ENUM:false_positive_risk}
      alternative_interpretation: "..."
      decision: drop
      drop_reason: "Контр-проверка (стр. 20–24): алгоритм обходит интервалы в порядке начала периода и явно сравнивает конец текущего интервала с началом следующего; std* соблюдён; риск пропуска разрыва не подтверждается."
    traces: []
    severity: null
    suggestion: null

summary: "..."
questions_to_author:
  - "..."
missing_context:
  - "..."
"""

_ENUM_TOKEN_TABLE: dict[str, str] = {
    "confidence": _join_args(ConfidenceLevel),
    "finding_source": _join_args(FindingSource),
    "verification_status": _join_args(VerificationStatus),
    "verification_summary": _join_args(VerificationSummary),
    "false_positive_risk": _join_args(FalsePositiveRisk),
    "self_check_decision": _join_args(SelfCheckDecision),
    "trace_status": _join_args(TraceStatus),
    "severity": _join_args(Severity),
    "severity_nullable": _join_args(Severity) + " | null",
}


_ENUM_TOKEN_PATTERN = re.compile(r"\{ENUM:([a-z_]+)\}")


def _resolve_enum_token(match: re.Match[str]) -> str:
    name = match.group(1)
    if name not in _ENUM_TOKEN_TABLE:
        raise KeyError(
            f"Неизвестный токен SGR-скелета: {{ENUM:{name}}}. "
            f"Добавь его в _ENUM_TOKEN_TABLE в prompt_fragments.py."
        )
    return _ENUM_TOKEN_TABLE[name]


def _render_skeleton_yaml(template: str) -> str:
    return _ENUM_TOKEN_PATTERN.sub(_resolve_enum_token, template)


def _wrap_skeleton_yaml_block(yaml_body: str) -> str:
    return "```yaml\n" + yaml_body + "```\n"


@lru_cache(maxsize=1)
def render_sgr_response_skeleton_body() -> str:
    """YAML-скелет тела ответа (findings … missing_context) в fenced-блоке."""
    return _wrap_skeleton_yaml_block(_render_skeleton_yaml(_RESPONSE_SKELETON_BODY_TEMPLATE))


# Сноска отображается в _review_info/review_prompt*.md после раздела
# ## Формат ответа.
_FIELD_CONSTRAINTS_NOTE = (
    "Пустые списки допустимы. Поля `findings[*].verification`, "
    "`findings[*].self_check.alternative_interpretation`, "
    "`findings[*].self_check.drop_reason`, `findings[*].severity`, "
    "`findings[*].suggestion` могут быть `null` в указанных условиях. "
    "Поле `findings[*].suggestion` обязательно и не может быть `null` "
    "при `self_check.decision: keep`; при `self_check.decision: drop` "
    "оно должно быть `null`. "
    "`findings[]` должен покрывать каждый candidate: для подтверждённого риска используй "
    "`self_check.decision: keep` с непустым `suggestion`, для отклонённого — "
    "`self_check.decision: drop` с непустым `drop_reason`. "
    "`findings[*].traces` обязателен у каждой finding: используй "
    "`traces: []`, если находка не связана с межстрочной трассой "
    "обязательства. Результат без ключа `traces` невалиден. "
    "Доказуемость межстрочной находки выражай связной трассой по всему "
    "видимому `-- new bsl --`: `satisfied` — обязательство закрыто и "
    "`satisfied_at` не `null`; `violated` — закрытие видимо отсутствует "
    "и `satisfied_at` может быть `null` или TARGET-строкой, связанной с "
    "проверкой/нарушением; `not_visible` — закрывающая строка не видна, "
    "`satisfied_at` может быть `null` или TARGET-строкой, которая "
    "создала/подсветила непроверяемое обязательство; факт фиксируй в "
    "`missing_context`, а не отдельной finding.\n"
)


def render_field_constraints_note() -> str:
    """Прозовая сноска под секцией «Формат ответа»."""
    return _FIELD_CONSTRAINTS_NOTE


__all__ = [
    "render_field_constraints_note",
    "render_focus_areas_list",
    "render_sgr_response_skeleton_body",
]
