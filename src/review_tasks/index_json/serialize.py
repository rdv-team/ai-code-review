"""Детерминированная сериализация модели в JSON.

Стабильная сортировка объектов/таблиц/индексов и стабильный порядок ключей дают
byte-identical вывод при неизменном target-ref. Порядок полей **внутри** индекса
значим (левый префикс) и не сортируется.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from .model import Index, IndexTable, ObjectIndexes


def _index_sort_key(index: Index) -> tuple[int, tuple[str, ...]]:
    # Кластерный индекс — первым; далее стабильно по составу полей.
    return (0 if index.clustered else 1, index.fields)


def _index_to_obj(index: Index) -> dict:
    return {"clustered": index.clustered, "fields": list(index.fields)}


def _table_to_obj(table: IndexTable) -> dict:
    indexes = sorted(table.indexes, key=_index_sort_key)
    return {"table": table.table, "indexes": [_index_to_obj(i) for i in indexes]}


def _object_to_obj(obj: ObjectIndexes) -> dict:
    tables = sorted(obj.tables, key=lambda t: t.table)
    return {
        "metadata": obj.metadata,
        "kind": obj.kind,
        "referenced_by": sorted(set(obj.referenced_by)),
        "tables": [_table_to_obj(t) for t in tables],
    }


def to_jsonable(objects: Iterable[ObjectIndexes]) -> dict:
    ordered = sorted(objects, key=lambda o: o.metadata)
    return {"objects": [_object_to_obj(o) for o in ordered]}


def dumps(objects: Iterable[ObjectIndexes]) -> str:
    """Вернуть детерминированный JSON-текст (UTF-8 совместимый, EOL нормализуется при записи)."""
    payload = to_jsonable(objects)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
