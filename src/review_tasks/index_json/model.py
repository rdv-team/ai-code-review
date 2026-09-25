"""Модель данных артефакта indexes.json.

Таблицы ключуются именем **физической** таблицы (`main`/`Итоги`/`ИтогиПоСчетам`/
`ИтогиМеждуСчетами`/`Субконто`/`Перерасчет`/`СрезПоследних`/`СрезПервых`/имя
табличной части). Виртуальные агрегаты запроса (`Остатки`/`Обороты`/
`ОстаткиИОбороты`) — НЕ ключи таблиц, а вход для маппинга на физическую таблицу
итогов (см. `query_scan`/`platform_rules`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
# Поле индекса — каноническое логическое имя 1С (Decision #5). Отдельный тип-алиас
# подчёркивает, что в `Index.fields` лежат именно нормализованные имена, без имён СУБД.
IndexField = str


@dataclass(frozen=True)
class FieldTypeEntry:
    """Один вариант типа поля 1С в порядке объявления в XML."""

    kind: str  # primitive | reference | value
    name: str
    string_length: int | None = None
    number_digits: int | None = None
    number_fraction_digits: int | None = None
    date_fractions: str | None = None


@dataclass(frozen=True)
class FieldType:
    """Компактное описание типа поля, включая составные типы."""

    entries: tuple[FieldTypeEntry, ...] = ()


@dataclass
class FieldDef:
    """Поле объекта метаданных в формате, независимом от исходной выгрузки."""

    name: str
    role: str  # dimension | resource | attribute
    indexing: str = "DontIndex"  # DontIndex | Index | IndexWithAdditionalOrder
    master: bool = False
    use_in_totals: bool = True
    base: bool = False
    type: FieldType = field(default_factory=FieldType)


@dataclass
class TabularSection:
    """Табличная часть нормализованного объекта метаданных."""

    name: str
    attributes: list[FieldDef] = field(default_factory=list)


@dataclass
class ParsedObject:
    """Минимальное описание объекта, потребляемое правилами и сериализаторами."""

    kind: str
    name: str
    dimensions: list[FieldDef] = field(default_factory=list)
    resources: list[FieldDef] = field(default_factory=list)
    attributes: list[FieldDef] = field(default_factory=list)
    tab_sections: list[TabularSection] = field(default_factory=list)
    code_length: int = 0
    description_length: int = 0
    number_length: int = 0
    hierarchical: bool = False
    folders_on_top: bool = True
    subordinate: bool = False
    default_presentation: str = ""
    periodic: bool = False
    recorder_subordinate: bool = False
    enable_slice_first: bool = False
    enable_slice_last: bool = False
    register_type: str = ""
    has_chart_of_accounts: bool = False
    correspondence: bool = False
    action_period: bool = False
    number_periodic: bool = False


@dataclass(frozen=True)
class Index:
    """Один индекс таблицы: упорядоченный список полей и признак кластерности."""

    fields: tuple[IndexField, ...]
    clustered: bool = False


@dataclass
class IndexTable:
    """Физическая таблица объекта и её индексы."""

    table: str
    indexes: list[Index] = field(default_factory=list)


@dataclass
class ObjectIndexes:
    """Описание индексов одного объекта метаданных."""

    metadata: str
    kind: str
    referenced_by: list[str] = field(default_factory=list)
    tables: list[IndexTable] = field(default_factory=list)


@dataclass
class ObjectMetadata:
    """Описание структуры одного объекта метаданных без копирования ParsedObject."""

    metadata: str
    kind: str
    parsed: ParsedObject
    referenced_by: list[str] = field(default_factory=list)
