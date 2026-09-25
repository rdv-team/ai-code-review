"""Обход критериев отбора XML/MDO — источник дополнительных индексов.

Один раз собираем карту: целевой объект / табличная часть / реквизит → доп. индекс.
Сам критерий отбора в indexes.json не попадает как отдельный объект-таблица
(Decision #6). При сборке индексов объекта подходящие записи добавляются движком
правил (`platform_rules`): для реквизита объекта — `Реквизит + Ссылка`, для реквизита
табличной части — `Реквизит + Ссылка` в таблице этой табличной части.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .config_xml import GitConfigSource
from .configurator_xml import filter_contents as configurator_filter_contents
from .edt_mdo import filter_contents as edt_filter_contents

# Английский вид метаданного в ссылке `<Content>` → каноническая русская форма.
_ENG_KIND = {
    "Catalog": "Справочник",
    "Document": "Документ",
    "InformationRegister": "РегистрСведений",
    "AccumulationRegister": "РегистрНакопления",
    "AccountingRegister": "РегистрБухгалтерии",
    "CalculationRegister": "РегистрРасчета",
    "ChartOfCharacteristicTypes": "ПланВидовХарактеристик",
    "ChartOfCalculationTypes": "ПланВидовРасчета",
}

# Карта: metadata → {None: реквизиты объекта, "ИмяТЧ": реквизиты табличной части}.
FilterIndexMap = dict[str, dict[str | None, set[str]]]


def _parse_ref(ref: str) -> tuple[str, str | None, str] | None:
    """Разобрать ссылку критерия в (metadata, табличная_часть|None, реквизит)."""
    parts = ref.split(".")
    if len(parts) < 4:
        return None
    kind = _ENG_KIND.get(parts[0])
    if not kind:
        return None
    metadata = f"{kind}.{parts[1]}"
    if parts[2] == "TabularSection" and len(parts) >= 6 and parts[4] == "Attribute":
        return metadata, parts[3], parts[5]
    if parts[2] == "Attribute":
        return metadata, None, parts[3]
    return None


def collect_filter_indexes(source: GitConfigSource, config_root: str) -> FilterIndexMap:
    """Построить карту доп. индексов из всех FilterCriteria конфигурации."""
    result: FilterIndexMap = {}
    sources = (
        (source.list_xml(config_root, "FilterCriteria"), configurator_filter_contents),
        (source.list_mdo(config_root, "FilterCriteria"), edt_filter_contents),
    )
    for paths, extract_contents in sources:
        for path in paths:
            try:
                root = ET.fromstring(source.read(path))
            except (FileNotFoundError, ET.ParseError):
                continue
            for content in extract_contents(root):
                parsed = _parse_ref(content)
                if parsed is None:
                    continue
                metadata, tab, attr = parsed
                result.setdefault(metadata, {}).setdefault(tab, set()).add(attr)
    return result
