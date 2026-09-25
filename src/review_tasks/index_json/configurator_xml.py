"""Адаптер XML-выгрузки Конфигуратора в общую модель metadata."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .model import FieldDef, FieldType, FieldTypeEntry, ParsedObject, TabularSection


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def filter_contents(root: ET.Element) -> list[str]:
    """Извлечь ссылки из XML-критерия отбора Конфигуратора."""
    return [
        item.text.strip()
        for item in root.iter()
        if _local(item.tag) == "Item" and item.text
    ]


def _child(el: ET.Element | None, name: str) -> ET.Element | None:
    if el is None:
        return None
    return next((child for child in el if _local(child.tag) == name), None)


def _ctext(el: ET.Element | None, name: str, default: str = "") -> str:
    child = _child(el, name)
    return child.text.strip() if child is not None and child.text else default


def _int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _opt_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _entry_kind(token: str) -> str:
    if token.startswith("cfg:") and "Ref." in token:
        return "reference"
    if token.startswith("xs:"):
        return "primitive"
    return "value"


def _parse_type(type_el: ET.Element | None) -> FieldType:
    """Нормализовать Type/TypeSet XML Конфигуратора без изменения результата."""
    if type_el is None:
        return FieldType()
    tokens: list[tuple[str, bool]] = []
    string_q = number_q = date_q = None
    for child in type_el:
        name = _local(child.tag)
        if name == "Type" and child.text:
            tokens.append((child.text.strip(), False))
        elif name == "TypeSet" and child.text:
            tokens.append((child.text.strip(), True))
        elif name == "StringQualifiers":
            string_q = child
        elif name == "NumberQualifiers":
            number_q = child
        elif name == "DateQualifiers":
            date_q = child

    entries: list[FieldTypeEntry] = []
    for token, is_typeset in tokens:
        if is_typeset:
            entries.append(FieldTypeEntry(kind="typeset", name=token))
            continue
        kwargs: dict[str, int | str | None] = {}
        if token == "xs:string" and string_q is not None:
            kwargs["string_length"] = _opt_int(_ctext(string_q, "Length"))
        elif token == "xs:decimal" and number_q is not None:
            kwargs["number_digits"] = _opt_int(_ctext(number_q, "Digits"))
            kwargs["number_fraction_digits"] = _opt_int(_ctext(number_q, "FractionDigits"))
        elif token == "xs:dateTime" and date_q is not None:
            kwargs["date_fractions"] = _ctext(date_q, "DateFractions") or None
        entries.append(FieldTypeEntry(kind=_entry_kind(token), name=token, **kwargs))
    return FieldType(entries=tuple(entries))


def _parse_field(node: ET.Element, role: str) -> FieldDef:
    props = _child(node, "Properties")
    use_in_totals = _child(props, "UseInTotals")
    return FieldDef(
        name=_ctext(props, "Name"), role=role,
        type=_parse_type(_child(props, "Type")),
        indexing=_ctext(props, "Indexing", "DontIndex") or "DontIndex",
        master=_ctext(props, "Master") == "true",
        use_in_totals=True if use_in_totals is None else (use_in_totals.text or "").strip() == "true",
        base=_ctext(props, "BaseDimension") == "true",
    )


def parse_object(kind: str, root: ET.Element | None) -> ParsedObject | None:
    """Разобрать XML Конфигуратора в модель, общую с EDT."""
    if root is None:
        return None
    obj_el = next(iter(root), None) if _local(root.tag) == "MetaDataObject" else root
    if obj_el is None:
        return None
    props = _child(obj_el, "Properties")
    if props is None:
        return None
    dimensions: list[FieldDef] = []
    resources: list[FieldDef] = []
    attributes: list[FieldDef] = []
    tab_sections: list[TabularSection] = []
    for node in _child(obj_el, "ChildObjects") or []:
        node_kind = _local(node.tag)
        if node_kind == "Dimension":
            dimensions.append(_parse_field(node, "dimension"))
        elif node_kind == "Resource":
            resources.append(_parse_field(node, "resource"))
        elif node_kind == "Attribute":
            attributes.append(_parse_field(node, "attribute"))
        elif node_kind == "TabularSection":
            tab_sections.append(TabularSection(
                name=_ctext(_child(node, "Properties"), "Name"),
                attributes=[_parse_field(item, "attribute") for item in _child(node, "ChildObjects") or [] if _local(item.tag) == "Attribute"],
            ))
    owners = _child(props, "Owners")
    return ParsedObject(
        kind=kind, name=_ctext(props, "Name"), dimensions=dimensions, resources=resources,
        attributes=attributes, tab_sections=tab_sections,
        code_length=_int(_ctext(props, "CodeLength")), description_length=_int(_ctext(props, "DescriptionLength")),
        number_length=_int(_ctext(props, "NumberLength")), hierarchical=_ctext(props, "Hierarchical") == "true",
        folders_on_top=_ctext(props, "FoldersOnTop", "true") != "false",
        subordinate=owners is not None and bool(list(owners)), default_presentation=_ctext(props, "DefaultPresentation"),
        periodic=kind == "РегистрСведений" and _ctext(props, "InformationRegisterPeriodicity", "Nonperiodical") != "Nonperiodical",
        recorder_subordinate=_ctext(props, "WriteMode") == "RecorderSubordinate",
        enable_slice_first=_ctext(props, "EnableTotalsSliceFirst") == "true",
        enable_slice_last=_ctext(props, "EnableTotalsSliceLast") == "true",
        register_type=_ctext(props, "RegisterType"), has_chart_of_accounts=bool(_ctext(props, "ChartOfAccounts")),
        correspondence=_ctext(props, "Correspondence") == "true", action_period=_ctext(props, "ActionPeriod") == "true",
        number_periodic=_ctext(props, "NumberPeriodicity", "Nonperiodical") != "Nonperiodical",
    )
