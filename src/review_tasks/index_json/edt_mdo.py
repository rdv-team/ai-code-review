"""Адаптер полных EDT `*.mdo` в общую модель metadata."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .model import FieldDef, FieldType, FieldTypeEntry, ParsedObject, TabularSection


class UnsupportedEdtDelta(ValueError):
    """MDO-дельта расширения не содержит полного описания объекта."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def filter_contents(root: ET.Element) -> list[str]:
    """Извлечь непосредственные ссылки из EDT-критерия отбора."""
    return [
        child.text.strip()
        for child in root
        if _local(child.tag) == "content" and child.text
    ]


def _children(el: ET.Element | None, name: str) -> list[ET.Element]:
    return [] if el is None else [child for child in el if _local(child.tag) == name]


def _child(el: ET.Element | None, name: str) -> ET.Element | None:
    return next(iter(_children(el, name)), None)


def _text(el: ET.Element | None, name: str, default: str = "") -> str:
    child = _child(el, name)
    return child.text.strip() if child is not None and child.text else default


def _bool(el: ET.Element | None, name: str, default: bool = False) -> bool:
    child = _child(el, name)
    if child is None or child.text is None:
        return default
    return child.text.strip().lower() == "true"


def _int(el: ET.Element | None, name: str) -> int:
    try:
        return int(_text(el, name))
    except ValueError:
        return 0


def _opt_int(el: ET.Element | None, name: str) -> int | None:
    try:
        return int(_text(el, name))
    except ValueError:
        return None


def _type_token(token: str) -> tuple[str, str]:
    primitives = {
        "String": "xs:string", "Number": "xs:decimal", "Date": "xs:dateTime", "Boolean": "xs:boolean",
    }
    if token in primitives:
        return "primitive", primitives[token]
    if "Ref." in token:
        return "reference", f"cfg:{token}"
    return "value", token


def _parse_type(type_el: ET.Element | None) -> FieldType:
    if type_el is None:
        return FieldType()
    string_q = _child(type_el, "stringQualifiers")
    number_q = _child(type_el, "numberQualifiers")
    date_q = _child(type_el, "dateQualifiers")
    entries: list[FieldTypeEntry] = []
    for type_node in _children(type_el, "types"):
        if not type_node.text:
            continue
        kind, name = _type_token(type_node.text.strip())
        kwargs: dict[str, int | str | None] = {}
        if name == "xs:string" and string_q is not None:
            kwargs["string_length"] = _opt_int(string_q, "length")
        elif name == "xs:decimal" and number_q is not None:
            kwargs["number_digits"] = _opt_int(number_q, "precision")
            # EDT допускает precision без scale; эквивалент XML тогда имеет 0.
            kwargs["number_fraction_digits"] = _opt_int(number_q, "scale")
            if kwargs["number_digits"] is not None and kwargs["number_fraction_digits"] is None:
                kwargs["number_fraction_digits"] = 0
        elif name == "xs:dateTime" and date_q is not None:
            kwargs["date_fractions"] = _text(date_q, "dateFractions") or None
        entries.append(FieldTypeEntry(kind=kind, name=name, **kwargs))
    return FieldType(entries=tuple(entries))


def _parse_field(node: ET.Element, role: str) -> FieldDef:
    return FieldDef(
        name=_text(node, "name"), role=role, type=_parse_type(_child(node, "type")),
        indexing=_text(node, "indexing", "DontIndex") or "DontIndex",
        master=_bool(node, "master"), use_in_totals=_bool(node, "useInTotals", True),
        base=_bool(node, "baseDimension"),
    )


def parse_object(kind: str, root: ET.Element | None) -> ParsedObject | None:
    """Разобрать полное EDT MDO; корневую дельту сообщить отдельной ошибкой."""
    if root is None:
        return None
    if "extendedConfigurationObject" in root.attrib:
        raise UnsupportedEdtDelta()

    dimensions = [_parse_field(node, "dimension") for node in _children(root, "dimensions")]
    resources = [_parse_field(node, "resource") for node in _children(root, "resources")]
    attributes = [_parse_field(node, "attribute") for node in _children(root, "attributes")]
    tab_sections = [
        TabularSection(
            name=_text(tab, "name"),
            attributes=[_parse_field(attr, "attribute") for attr in _children(tab, "attributes")],
        )
        for tab in _children(root, "tabularSections")
    ]
    periodicity = _text(root, "periodicity", "Nonperiodical")
    register_type = _text(root, "registerType", "Balance") if kind == "РегистрНакопления" else ""
    if register_type == "Turnover":
        register_type = "Turnovers"
    return ParsedObject(
        kind=kind, name=_text(root, "name"), dimensions=dimensions, resources=resources,
        attributes=attributes, tab_sections=tab_sections,
        code_length=_int(root, "codeLength"), description_length=_int(root, "descriptionLength"),
        number_length=_int(root, "numberLength"),
        hierarchical=_bool(root, "hierarchical") or _int(root, "levelCount") > 0,
        folders_on_top=_bool(root, "foldersOnTop", True),
        subordinate=bool(_children(root, "owners")), default_presentation=_text(root, "defaultPresentation"),
        periodic=kind == "РегистрСведений" and periodicity not in {"", "Nonperiodical"},
        recorder_subordinate=_text(root, "writeMode") == "RecorderSubordinate",
        enable_slice_first=_bool(root, "enableTotalsSliceFirst"), enable_slice_last=_bool(root, "enableTotalsSliceLast"),
        register_type=register_type,
        has_chart_of_accounts=bool(_text(root, "chartOfAccounts")), correspondence=_bool(root, "correspondence"),
        action_period=_bool(root, "actionPeriod"),
        number_periodic=_text(root, "numberPeriodicity", "Nonperiodical") != "Nonperiodical",
    )
