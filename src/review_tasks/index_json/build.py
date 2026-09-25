"""Сборка артефактов indexes.json/metadata.json: сканирование → XML → модели → JSON.

Вызывается из генерации prompt-артефактов `init` (где доступны `target`,
`bsl_paths`, `review_dir`). XML конфигурации читается из target-ref и на диск не
сохраняется — пишутся только файлы в `_review_info`. При отсутствии пригодных
источников пишется пустой список объектов без ошибки.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from ..infrastructure.text_files import read_text_safe, write_text_lf
from .config_xml import GitConfigSource
from .filter_criteria import FilterIndexMap, collect_filter_indexes
from .edt_mdo import UnsupportedEdtDelta
from .model import ObjectIndexes, ObjectMetadata, ParsedObject
from .platform_rules import KIND_JSON, build_table, map_suffix_to_table
from .query_scan import scan_module
from .serialize import dumps as dumps_indexes
from .serialize_metadata import dumps as dumps_metadata


@dataclass
class _Grouped:
    suffixes: set[str | None] = field(default_factory=set)
    refs: set[str] = field(default_factory=set)


@dataclass
class ParsedSource:
    metadata: str
    kind_json: str
    referenced_by: list[str]
    suffixes: set[str | None]
    parsed: ParsedObject


def _scan_sources(
    review_dir: Path,
    bsl_paths: list[str],
) -> dict[tuple[str, str], _Grouped]:
    """Собрать источники запросов из изменённых BSL.

    Изменённые модули сканируются целиком: `bsl_paths` уже ограничен файлами,
    затронутыми задачей, поэтому источники собираются по всему тексту каждого
    такого модуля. Это надёжнее фильтрации по конкретным изменённым строкам —
    источник `ИЗ ...` мог остаться контекстом, пока менялись `ГДЕ`/поля выборки.
    """
    grouped: dict[tuple[str, str], _Grouped] = {}
    for rel in bsl_paths:
        abs_path = review_dir / rel
        if not abs_path.is_file():
            continue
        posix = rel.replace("\\", "/")
        for ref in scan_module(read_text_safe(abs_path)):
            entry = grouped.setdefault((ref.kind, ref.name), _Grouped())
            entry.suffixes.add(ref.suffix)
            entry.refs.add(f"{posix}:{ref.line}")
    return grouped


def iter_parsed_sources(
    review_dir: Path | str,
    bsl_paths: list[str],
    *,
    source: GitConfigSource,
    config_root: str,
) -> Iterator[ParsedSource]:
    """Единый проход: BSL-источники → XML объекта → ParsedObject.

    `source` и `config_root` создаются один раз на источник вызывающим кодом и
    разделяются с `indexes_from_parsed` (общий кэш `tree()`).
    """
    review_dir = Path(review_dir)
    grouped = _scan_sources(review_dir, bsl_paths)
    if not grouped:
        return

    for (kind, name), entry in grouped.items():
        try:
            parsed = source.load_parsed_object(config_root, kind, name)
        except UnsupportedEdtDelta:
            print(
                f"indexes.json: EDT-дельта объекта {kind}.{name} не поддерживается — пропущена",
                file=sys.stderr,
            )
            continue
        if parsed is None:
            # Нерезолвленный объект (XML не найден или не распарсился): логируем и
            # пропускаем, не прерывая генерацию остальных. Фиксируем факт в stderr,
            # а не статус-полем в модели — чтобы пропуск не был молчаливым.
            print(
                f"indexes.json: объект {kind}.{name} не резолвится из {source.target} — пропущен",
                file=sys.stderr,
            )
            continue
        parsed_kind = parsed.kind or kind
        parsed_name = parsed.name or name
        yield ParsedSource(
            metadata=f"{parsed_kind}.{parsed_name}",
            kind_json=KIND_JSON.get(parsed_kind, parsed_kind),
            referenced_by=sorted(entry.refs),
            suffixes=set(entry.suffixes),
            parsed=parsed,
        )


def object_indexes_from(
    parsed_source: ParsedSource,
    filter_map: FilterIndexMap,
) -> ObjectIndexes | None:
    """Построить индексный объект из уже распарсенного источника."""
    obj_filter = filter_map.get(parsed_source.metadata, {})
    filter_main = obj_filter.get(None, set())
    filter_tabs = {k: v for k, v in obj_filter.items() if k is not None}

    table_names: list[str] = []
    for suffix in parsed_source.suffixes:
        name_t = map_suffix_to_table(parsed_source.parsed, suffix)
        if name_t not in table_names:
            table_names.append(name_t)

    tables = [
        t for t in (
            build_table(parsed_source.parsed, tn, filter_main=filter_main, filter_tabs=filter_tabs)
            for tn in table_names
        )
        if t is not None
    ]
    if not tables:
        return None

    return ObjectIndexes(
        metadata=parsed_source.metadata,
        kind=parsed_source.kind_json,
        referenced_by=parsed_source.referenced_by,
        tables=tables,
    )


def object_metadata_from(parsed_source: ParsedSource) -> ObjectMetadata:
    """Построить metadata-объект без копирования ParsedObject."""
    return ObjectMetadata(
        metadata=parsed_source.metadata,
        kind=parsed_source.kind_json,
        parsed=parsed_source.parsed,
        referenced_by=parsed_source.referenced_by,
    )


def indexes_from_parsed(
    parsed_sources: list[ParsedSource],
    *,
    source: GitConfigSource,
    config_root: str,
) -> list[ObjectIndexes]:
    """Построить индексные объекты из общего списка ParsedSource.

    `source`/`config_root` — те же экземпляры, что переданы в
    `iter_parsed_sources` (кэш `tree()` разделяется).
    """
    if not parsed_sources:
        return []

    filter_map = collect_filter_indexes(source, config_root)

    objects: list[ObjectIndexes] = []
    for parsed_source in parsed_sources:
        obj = object_indexes_from(parsed_source, filter_map)
        if obj is not None:
            objects.append(obj)
    return objects


def write_indexes_objects(
    review_dir: Path | str,
    objects: list[ObjectIndexes],
) -> Path:
    """Записать уже построенную модель индексов в `<review_dir>/_review_info/indexes.json`.

    Используется multi-repo путём `init`: индексы каждого репозитория строятся
    отдельно (в его собственном worktree и target-ref), затем агрегируются и
    пишутся одним детерминированным файлом.
    """
    out_path = Path(review_dir) / "_review_info" / "indexes.json"
    write_text_lf(out_path, dumps_indexes(objects))
    return out_path


def write_metadata_objects(
    review_dir: Path | str,
    objects: list[ObjectMetadata],
) -> Path:
    """Записать уже построенную модель в `<review_dir>/_review_info/metadata.json`."""
    out_path = Path(review_dir) / "_review_info" / "metadata.json"
    write_text_lf(out_path, dumps_metadata(objects))
    return out_path
