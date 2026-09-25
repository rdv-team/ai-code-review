"""Зашитый движок платформенных правил построения индексов 1С.

Правила перенесены в код как таблицы решений по виду объекта и его свойствам.
Источник истины при расхождении человекочитаемых `.md` и реальной платформы —
оракул `indexes.xlsx` (Decision #5). Известные расхождения, воспроизводимые здесь:
- документы: индекс по дате — `Дата + Ссылка + ПометкаУдаления` (а не `Дата + Ссылка`);
- таблицы итогов: поля-разделители (`_Splitter`/независимые разделители) и
  `ХэшИзмерений` НЕ выводятся (Non-Goal) — индекс сравнивается по прикладным полям.

Файлы `*.md`/`indexes.md`/`indexes.xlsx` здесь НЕ читаются — все правила универсальны.
"""

from __future__ import annotations

from .model import FieldDef, Index, IndexTable, ParsedObject, TabularSection

# Вид метаданного → значение поля `kind` в JSON.
KIND_JSON = {
    "Справочник": "catalog",
    "Документ": "document",
    "РегистрСведений": "informationRegister",
    "РегистрНакопления": "accumulationRegister",
    "РегистрБухгалтерии": "accountingRegister",
    "РегистрРасчета": "calculationRegister",
    "ПланВидовХарактеристик": "chartOfCharacteristicTypes",
    "ПланВидовРасчета": "chartOfCalculationTypes",
}

_REF = "Ссылка"


# ---------------------------------------------------------------------------
# Накопитель индексов (уникальность + ровно один кластерный)
# ---------------------------------------------------------------------------

class _IndexSet:
    def __init__(self) -> None:
        self._fields: dict[tuple[str, ...], bool] = {}

    def add(self, fields: list[str], clustered: bool = False) -> None:
        key = tuple(fields)
        if not key:
            return
        self._fields[key] = self._fields.get(key, False) or clustered

    def to_indexes(self) -> list[Index]:
        return [Index(fields=f, clustered=c) for f, c in self._fields.items()]


# ---------------------------------------------------------------------------
# Сопоставление суффикса виртуальной таблицы → физическая таблица (Decision #3)
# ---------------------------------------------------------------------------

def map_suffix_to_table(parsed: ParsedObject, suffix: str | None) -> str:
    """Вернуть имя физической таблицы для суффикса источника (или 'main')."""
    if not suffix:
        return "main"
    s = suffix.lower()
    kind = parsed.kind
    if kind == "РегистрНакопления":
        if s in {"остатки", "обороты", "остаткииобороты"}:
            return "Итоги"
    elif kind == "РегистрБухгалтерии":
        if s in {"остатки", "обороты", "остаткииобороты"}:
            return "ИтогиПоСчетам"
        if s == "оборотыдткт":
            return "ИтогиМеждуСчетами"
        if s == "движенияссубконто":
            return "Субконто"
    elif kind == "РегистрРасчета":
        if s == "перерасчет":
            return "Перерасчет"
        # ФактическийПериодДействия/БазаРегистра/ДанныеГрафика вычисляются поверх
        # основной таблицы; отдельной проверенной оракулом таблицы пока нет
        # (follow-up до появления фикстуры-оракула) — описываем основную.
        return "main"
    elif kind == "РегистрСведений":
        # Срез образует отдельную физическую таблицу лишь при включённых итогах,
        # но её правила не покрыты оракулом — пока описываем основную таблицу
        # (follow-up до фикстуры-оракула на enabled-срез). Главное: не возвращать
        # имя таблицы, для которой нет builder'а, иначе объект молча исчезнет.
        return "main"
    for tab in parsed.tab_sections:
        if tab.name.lower() == s:
            return tab.name
    return "main"  # нераспознанный суффикс — основная таблица


# ---------------------------------------------------------------------------
# Правила по видам объектов
# ---------------------------------------------------------------------------

def _build_reference_main(parsed: ParsedObject, filter_main: set[str]) -> _IndexSet:
    """Справочник / план видов характеристик / план видов расчёта / план обмена."""
    s = _IndexSet()
    s.add([_REF], clustered=True)
    s.add(["ИмяПредопределенныхДанных"])
    has_code = parsed.code_length > 0
    has_desc = parsed.description_length > 0
    repr_field = "Код" if parsed.default_presentation == "AsCode" else "Наименование"

    def emit(prefix: list[str]) -> None:
        if has_code:
            s.add(prefix + ["Код", _REF])
        if has_desc:
            s.add(prefix + ["Наименование", _REF])
        if prefix and not has_code and not has_desc:
            s.add(prefix + [_REF])
        for a in parsed.attributes:
            if a.indexing == "IndexWithAdditionalOrder":
                s.add(prefix + [a.name, repr_field, _REF])
                s.add(prefix + [a.name, _REF])
            elif a.indexing == "Index":
                s.add(prefix + [a.name, _REF])

    emit([])
    if parsed.subordinate:
        owner = ["Владелец"]
        if has_code:
            s.add(owner + ["Код", _REF])
        else:
            s.add(owner + [_REF])
        if has_desc:
            s.add(owner + ["Наименование", _REF])
        for a in parsed.attributes:
            if a.indexing != "DontIndex":
                s.add(owner + [a.name, _REF])
    if parsed.hierarchical:
        emit(["Родитель"] + (["ЭтоГруппа"] if parsed.folders_on_top else []))
    for attr in sorted(filter_main):
        s.add([attr, _REF])
    return s


def _build_document_main(parsed: ParsedObject, filter_main: set[str]) -> _IndexSet:
    s = _IndexSet()
    s.add([_REF], clustered=True)
    if parsed.number_length > 0:
        s.add(["Номер", _REF])
    # Оракул: индекс по дате включает ПометкаУдаления (расхождение с .md).
    s.add(["Дата", _REF, "ПометкаУдаления"])
    if parsed.number_periodic and parsed.number_length > 0:
        s.add(["ПрефиксНомера", "Номер", _REF])
    for a in parsed.attributes:
        if a.indexing == "IndexWithAdditionalOrder":
            s.add([a.name, "Дата", _REF])
            s.add([a.name, _REF])
        elif a.indexing == "Index":
            s.add([a.name, _REF])
    for attr in sorted(filter_main):
        s.add([attr, _REF])
    return s


def _build_information_main(parsed: ParsedObject, filter_main: set[str]) -> _IndexSet:
    s = _IndexSet()
    dims = [d.name for d in parsed.dimensions]
    if parsed.recorder_subordinate:
        s.add(["Регистратор", "НомерСтроки"], clustered=True)
        return s
    period = ["Период"] if parsed.periodic else []
    if dims:
        if parsed.periodic:
            s.add(["Период"] + dims)            # Период + Измерения (всегда)
            s.add(dims + ["Период"], clustered=True)  # Измерения + Период (кластерный)
        else:
            s.add(dims, clustered=True)          # Измерения (кластерный)
    elif parsed.periodic:
        s.add(["Период"], clustered=True)
    # Ведущее/индексируемое измерение впереди (не первое/единственное).
    if len(dims) > 1:
        for idx, d in enumerate(parsed.dimensions):
            if idx == 0:
                continue
            if d.master or d.indexing != "DontIndex":
                others = [x for x in dims if x != d.name]
                s.add([d.name] + period + others)
    for a in parsed.attributes:
        if a.indexing != "DontIndex":
            s.add([a.name] + period + dims)
    for r in parsed.resources:
        if r.indexing != "DontIndex":
            s.add([r.name] + period + dims)
    for attr in sorted(filter_main):
        s.add([attr] + period + dims)
    return s


def _build_register_main(parsed: ParsedObject, filter_main: set[str], period: str) -> _IndexSet:
    """Основная таблица регистра накопления (period='Период')."""
    s = _IndexSet()
    base = [period, "Регистратор", "НомерСтроки"]
    s.add(base, clustered=True)
    s.add(["Регистратор", "НомерСтроки"])
    for d in parsed.dimensions:
        if d.indexing != "DontIndex":
            s.add([d.name] + base)
    for a in parsed.attributes:
        if a.indexing != "DontIndex":
            s.add([a.name] + base)
    for attr in sorted(filter_main):
        s.add([attr] + base)
    return s


def _build_accounting_main(parsed: ParsedObject, filter_main: set[str]) -> _IndexSet:
    s = _build_register_main(parsed, filter_main, "Период")
    if parsed.has_chart_of_accounts:
        if parsed.correspondence:
            s.add(["СчетДт", "Период", "Регистратор"])
            s.add(["СчетКт", "Период", "Регистратор"])
        else:
            s.add(["Счет", "Период", "Регистратор"])
    return s


def _build_calc_main(parsed: ParsedObject, filter_main: set[str]) -> _IndexSet:
    s = _IndexSet()
    pr = "ПериодРегистрации"
    base = [pr, "Регистратор", "НомерСтроки"]
    s.add(base, clustered=True)
    s.add(["Регистратор", "НомерСтроки"])
    base_dims = [d.name for d in parsed.dimensions if d.base]
    s.add([pr] + base_dims)                    # ПериодРегистрации + базовые (всегда)
    if base_dims:
        s.add(base_dims + [pr])                # базовые + ПериодРегистрации
    if parsed.action_period:
        s.add(["ПериодДействия"] + base_dims)
        if base_dims:
            s.add(base_dims + ["ПериодДействия"])
    for d in parsed.dimensions:
        if d.indexing != "DontIndex":
            s.add([d.name] + base)
    for a in parsed.attributes:
        if a.indexing != "DontIndex":
            s.add([a.name] + base)
    for attr in sorted(filter_main):
        s.add([attr] + base)
    return s


def _build_main(parsed: ParsedObject, filter_main: set[str]) -> _IndexSet:
    kind = parsed.kind
    if kind in {"Справочник", "ПланВидовХарактеристик", "ПланВидовРасчета"}:
        return _build_reference_main(parsed, filter_main)
    if kind == "Документ":
        return _build_document_main(parsed, filter_main)
    if kind == "РегистрСведений":
        return _build_information_main(parsed, filter_main)
    if kind == "РегистрНакопления":
        return _build_register_main(parsed, filter_main, "Период")
    if kind == "РегистрБухгалтерии":
        return _build_accounting_main(parsed, filter_main)
    if kind == "РегистрРасчета":
        return _build_calc_main(parsed, filter_main)
    return _IndexSet()


def _build_accum_totals(parsed: ParsedObject) -> _IndexSet:
    s = _IndexSet()
    dims = [d.name for d in parsed.dimensions if d.use_in_totals]
    s.add(["Период"] + dims, clustered=True)
    for idx, d in enumerate(parsed.dimensions):
        if idx == 0 or not d.use_in_totals or d.indexing == "DontIndex":
            continue
        if parsed.register_type == "Turnovers":
            s.add([d.name, "Период"])
        else:
            s.add(["Период", d.name])
    return s


def _build_acc_totals(parsed: ParsedObject) -> _IndexSet:
    s = _IndexSet()
    fields = ["Период"]
    if parsed.has_chart_of_accounts:
        fields.append("Счет")
    fields += [d.name for d in parsed.dimensions if d.use_in_totals]
    s.add(fields, clustered=True)
    return s


def _build_acc_between(parsed: ParsedObject) -> _IndexSet:
    s = _IndexSet()
    dims = [d.name for d in parsed.dimensions if d.use_in_totals]
    if dims:
        s.add(dims, clustered=True)
    return s


def _build_acc_subconto(parsed: ParsedObject) -> _IndexSet:
    s = _IndexSet()
    s.add(["Период", "Регистратор", "НомерСтроки", "ВидСубконто", "Корреспонденция"], clustered=True)
    s.add(["Регистратор", "НомерСтроки", "Корреспонденция"])
    s.add(["ВидСубконто", "Значение"])
    return s


def _build_recalc(parsed: ParsedObject) -> _IndexSet:
    s = _IndexSet()
    s.add(["Регистратор", "ВидРасчета"], clustered=True)
    return s


def _build_tab_section(parsed: ParsedObject, tab: TabularSection, filter_attrs: set[str]) -> _IndexSet:
    s = _IndexSet()
    s.add([_REF, "Ключ"], clustered=True)
    for a in tab.attributes:
        if a.indexing != "DontIndex" or a.name in filter_attrs:
            s.add([a.name, _REF])
    return s


_TOTALS_BUILDERS = {
    "Итоги": _build_accum_totals,
    "ИтогиПоСчетам": _build_acc_totals,
    "ИтогиМеждуСчетами": _build_acc_between,
    "Субконто": _build_acc_subconto,
    "Перерасчет": _build_recalc,
}


def build_table(
    parsed: ParsedObject,
    table_name: str,
    *,
    filter_main: set[str],
    filter_tabs: dict[str, set[str]],
) -> IndexTable | None:
    """Построить одну физическую таблицу объекта (или None, если индексов нет)."""
    if table_name == "main":
        index_set = _build_main(parsed, filter_main)
    elif table_name in _TOTALS_BUILDERS:
        index_set = _TOTALS_BUILDERS[table_name](parsed)
    else:
        tab = next((t for t in parsed.tab_sections if t.name == table_name), None)
        if tab is None:
            return None
        index_set = _build_tab_section(parsed, tab, filter_tabs.get(table_name, set()))
    indexes = index_set.to_indexes()
    if not indexes:
        return None
    return IndexTable(table=table_name, indexes=indexes)
