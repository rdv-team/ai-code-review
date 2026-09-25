"""Детерминированная генерация артефакта `_review_info/indexes.json`.

Пакет на чистом Python (stdlib-only) строит описание таблиц индексов и порядка их
полей для объектов метаданных 1С, на которые ссылаются изменённые тексты запросов.

Состав:
- `query_scan`    — сканер источников данных из BSL (якоря `ИЗ`/`СОЕДИНЕНИЕ`);
- `config_xml`    — резолв `configRoot` и чтение/парсинг XML конфигурации из git-ref;
- `platform_rules`— зашитый движок платформенных правил построения индексов;
- `filter_criteria` — обход `FilterCriteria/*.xml` (доп. индексы по критериям отбора);
- `model` + `serialize*` — модель данных и детерминированная сериализация JSON.

Правила платформы зашиты в код универсально; справочники `*.md`/`indexes.md` и
оракул `indexes.xlsx` используются только при разработке и в тестах и в рантайме
никогда не читаются.
"""

from __future__ import annotations

from .build import write_indexes_objects, write_metadata_objects
from .model import ObjectIndexes, ObjectMetadata

__all__ = [
    "ObjectIndexes",
    "ObjectMetadata",
    "write_indexes_objects",
    "write_metadata_objects",
]
