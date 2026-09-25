"""Закрытые перечисления значений SGR YAML-ответа и каталог 12 областей.

Этот модуль — единый источник истины для всех ``Literal``-типов и
описаний фокус-областей. После завершения миграции (Phase 2) python-кортежи
с теми же значениями НЕ должны существовать в ``review_yaml.py`` или
других местах вне ``sgr_schema/``.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

ConfidenceLevel = Literal["high", "medium", "low"]
ChangeType = Literal[
    "feature",
    "bugfix",
    "refactor",
    "performance",
    "integration",
    "security_fix",
    "data_model",
    "unclear",
]
FindingSource = Literal[
    "ai_knowledge",
    "trigger_match",
    "std",
    "rdv",
    "ssl",
    "platform_docs",
    "v8std",
    "mixed",
]
SelfCheckDecision = Literal["keep", "drop"]
FalsePositiveRisk = Literal["low", "medium", "high"]
TraceStatus = Literal["satisfied", "violated", "not_visible"]
VerificationStatus = Literal["applied", "unavailable"]
VerificationSummary = Literal["verified", "limited_unverified", "self_evident"]
Severity = Literal["critical", "important", "desirable"]

FocusArea = Literal[
    "correctness",
    "data_integrity",
    "transactions_locks",
    "performance_query",
    "performance_collection",
    "client_server",
    "forms_ui",
    "security",
    "error_handling",
    "integrations_exchange",
    "standards",
    "deviations",
]

class FocusAreaMeta(NamedTuple):
    """Метаданные одной SGR-области.

    ``source_hint`` указывает либо на стандарты в репозитории
    (``dev-standarts/*``, ``platform-database-indexes/*``), либо на общую
    базу знаний — используется промптом и человеком при объяснении
    выбора области.
    """

    name: FocusArea
    description: str
    source_hint: str


# Порядок этого кортежа — канонический порядок SGR-областей и используется
# в ``prompt_fragments.render_focus_areas_list()`` для генерации списка
# schema-derived candidate inventory in staged prompt templates. Поле
# ``source_hint`` хранит готовый Markdown-фрагмент (с backticks вокруг
# path-глобов), потому что его рендер в промпт идёт без дополнительного
# форматирования.
FOCUS_AREA_CATALOG: tuple[FocusAreaMeta, ...] = (
    FocusAreaMeta(
        name="correctness",
        description=(
            "Логические баги, когда выполнение кода может привести к "
            "некорректному результату или ошибке."
        ),
        source_hint="общие знания LLM",
    ),
    FocusAreaMeta(
        name="data_integrity",
        description="Корректность хранения, согласованность реквизитов.",
        source_hint="`dev-standarts/05-*`",
    ),
    FocusAreaMeta(
        name="transactions_locks",
        description=(
            "Транзакции, управляемые блокировки, взаимоблокировки, "
            "таймауты на блокировках."
        ),
        source_hint="`dev-standarts/04-*`",
    ),
    FocusAreaMeta(
        name="performance_query",
        description=(
            "Запросы в цикле, индексы БД, виртуальные таблицы, "
            "соединения таблиц, динамические списки."
        ),
        source_hint=(
            "`dev-standarts/01-*`, `dev-standarts/02-*`, "
            "`dev-standarts/03-*` и `platform-database-indexes/*`"
        ),
    ),
    FocusAreaMeta(
        name="performance_collection",
        description="Таблицы значений, поиск, индексы ТЗ.",
        source_hint="`dev-standarts/11-*`",
    ),
    FocusAreaMeta(
        name="client_server",
        description=(
            "`&НаКлиенте`/`&НаСервере`, серверные вызовы, длительные операции."
        ),
        source_hint="`dev-standarts/06-*`",
    ),
    FocusAreaMeta(
        name="forms_ui",
        description=(
            "Элементы формы, `ТекущиеДанные`, `ОбработкаПроверкиЗаполнения`, "
            "параметр `Отказ`, программное изменение реквизитов."
        ),
        source_hint="`dev-standarts/07-*`, `dev-standarts/08-*`",
    ),
    FocusAreaMeta(
        name="security",
        description=(
            "`Выполнить`/`Вычислить`, файлы, пароли, HTTP/FTP-соединения, "
            "внешние компоненты."
        ),
        source_hint="`dev-standarts/09-*`",
    ),
    FocusAreaMeta(
        name="error_handling",
        description=(
            "`Попытка`/`Исключение`, информативность ошибок, откат после ошибки."
        ),
        source_hint="`dev-standarts/10-*`",
    ),
    FocusAreaMeta(
        name="integrations_exchange",
        description=(
            "`ОбменДанными.Загрузка`, проведение зависимых документов в "
            "очередь, фоновые задания, HTTP-интеграции."
        ),
        source_hint=(
            "`_review_info/reference-catalog.json` → релевантная локальная "
            "карточка `dev-standarts/08-*` (rdv3), встроенная карта имён "
            "`.agents/skills/mcp-review-verification/references/ssl-library-search.md` "
            "без активации skill и MCP"
        ),
    ),
    FocusAreaMeta(
        name="standards",
        description=(
            "Нарушения вендорских стандартов разработки 1С v8std "
            "и проектных стандартов RDV."
        ),
        source_hint=(
            "`_review_info/reference-catalog.json` → релевантные локальные "
            "карточки `dev-standarts/*`, встроенная карта имён "
            "`.agents/skills/mcp-review-verification/references/ssl-library-search.md` "
            "без активации skill и MCP, проектные стандарты RDV"
        ),
    ),
    FocusAreaMeta(
        name="deviations",
        description=(
            "Отклонения от функционального описания задачи или "
            "синтезированной бизнес-гипотезы."
        ),
        source_hint="описание задачи, сообщения коммитов и видимый код",
    ),
)


__all__ = [
    "ChangeType",
    "ConfidenceLevel",
    "FalsePositiveRisk",
    "FOCUS_AREA_CATALOG",
    "FindingSource",
    "FocusArea",
    "FocusAreaMeta",
    "SelfCheckDecision",
    "Severity",
    "TraceStatus",
    "VerificationStatus",
    "VerificationSummary",
]
