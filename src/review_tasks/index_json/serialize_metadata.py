"""Детерминированная сериализация структуры объектов в metadata.json."""

from __future__ import annotations

import json
from collections.abc import Iterable

from .model import FieldDef, FieldType, FieldTypeEntry, ObjectMetadata, ParsedObject, TabularSection


_REF_PREFIXES = {
    "CatalogRef": "СправочникСсылка",
    "DocumentRef": "ДокументСсылка",
    "EnumRef": "ПеречислениеСсылка",
    "ChartOfCharacteristicTypesRef": "ПланВидовХарактеристикСсылка",
    "ChartOfAccountsRef": "ПланСчетовСсылка",
    "ChartOfCalculationTypesRef": "ПланВидовРасчетаСсылка",
    "BusinessProcessRef": "БизнесПроцессСсылка",
    "TaskRef": "ЗадачаСсылка",
    "ExchangePlanRef": "ПланОбменаСсылка",
}

_DATE_FRACTIONS = {
    "Date": "Дата",
    "DateTime": "ДатаВремя",
    "Time": "Время",
}

_ACCUMULATION_REGISTER_TYPES = {
    "Balance": "Остатки",
    "Balances": "Остатки",
    "Turnover": "Обороты",
    "Turnovers": "Обороты",
}


def _strip_known_prefix(token: str) -> str:
    for prefix in ("xs:", "v8:", "cfg:"):
        if token.startswith(prefix):
            return token[len(prefix):]
    return token


def _render_reference(token: str) -> str:
    raw = token.removeprefix("cfg:")
    prefix, sep, name = raw.partition(".")
    mapped = _REF_PREFIXES.get(prefix)
    if mapped and sep:
        return f"{mapped}.{name}"
    return raw


def _render_entry(entry: FieldTypeEntry) -> str:
    token = entry.name
    if entry.kind == "typeset":
        # ОпределяемыйТип/системный набор — выводим токен как есть (`cfg:DefinedType.Имя`).
        return token
    if entry.kind == "reference":
        return _render_reference(token)
    if token == "xs:string":
        if entry.string_length is not None and entry.string_length > 0:
            return f"Строка({entry.string_length})"
        return "Строка"
    if token == "xs:decimal":
        if entry.number_digits is None:
            return "Число"
        if entry.number_fraction_digits is None:
            return f"Число({entry.number_digits})"
        return f"Число({entry.number_digits},{entry.number_fraction_digits})"
    if token == "xs:dateTime":
        return _DATE_FRACTIONS.get(entry.date_fractions or "Date", "Дата")
    if token == "xs:boolean":
        return "Булево"
    return _strip_known_prefix(token)


def _render_type(field_type: FieldType) -> str | list[str]:
    rendered = [_render_entry(entry) for entry in field_type.entries]
    if not rendered:
        return "Неизвестно"
    if len(rendered) == 1:
        return rendered[0]
    return rendered


def _field_to_obj(field: FieldDef) -> dict:
    result = {
        "name": field.name,
        "type": _render_type(field.type),
    }
    if field.indexing != "DontIndex":
        result["indexed"] = True
    return result


def _fields_to_obj(fields: list[FieldDef]) -> list[dict]:
    return [_field_to_obj(field) for field in fields]


def _tabular_section_to_obj(tab: TabularSection) -> dict | None:
    attrs = _fields_to_obj(tab.attributes)
    if not attrs:
        return None
    return {
        "name": tab.name,
        "attributes": attrs,
    }


def _add_field_groups(result: dict, parsed: ParsedObject) -> None:
    groups = (
        ("dimensions", parsed.dimensions),
        ("resources", parsed.resources),
        ("attributes", parsed.attributes),
    )
    for key, fields in groups:
        if fields:
            result[key] = _fields_to_obj(fields)

    tab_sections = [
        item for item in (_tabular_section_to_obj(tab) for tab in parsed.tab_sections)
        if item is not None
    ]
    if tab_sections:
        result["tabular_sections"] = tab_sections


def _add_register_flags(result: dict, parsed: ParsedObject) -> None:
    if parsed.kind == "РегистрСведений":
        if parsed.periodic:
            result["periodic"] = True
        if parsed.recorder_subordinate:
            result["recorder_subordinate"] = True
    elif parsed.kind == "РегистрНакопления" and parsed.register_type:
        result["register_type"] = _ACCUMULATION_REGISTER_TYPES.get(
            parsed.register_type,
            parsed.register_type,
        )


def _object_to_obj(obj: ObjectMetadata) -> dict:
    result = {
        "metadata": obj.metadata,
        "kind": obj.kind,
        "referenced_by": sorted(set(obj.referenced_by)),
    }
    _add_register_flags(result, obj.parsed)
    _add_field_groups(result, obj.parsed)
    return result


def to_jsonable(objects: Iterable[ObjectMetadata]) -> dict:
    ordered = sorted(objects, key=lambda o: o.metadata)
    return {"objects": [_object_to_obj(o) for o in ordered]}


def dumps(objects: Iterable[ObjectMetadata]) -> str:
    """Вернуть детерминированный JSON-текст metadata.json."""
    payload = to_jsonable(objects)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
