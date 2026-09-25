"""Сканер источников данных из текста запросов в BSL.

Идея (Decision #3): собираем токен только в позиции источника — после `ИЗ` и после
`… СОЕДИНЕНИЕ` — и только если его левая часть до точки ∈ множеству ключевых слов
вида метаданного. Это отсекает `ЗНАЧЕНИЕ(Справочник.X.ПустаяСсылка)`,
`ВЫРАЗИТЬ(... КАК Документ.X)`, навигацию `Псевдоним.Поле`, временные таблицы
`ВТ_*`, параметры `&Имя` и псевдонимы.

Текст запроса в BSL «обёрнут» в строковые литералы: предварительно разворачиваем
обвязку (склейка соседних литералов, снятие префикса `|` строк-продолжения,
сохранение переносов как разделителей) и параллельно ведём карту «позиция → строка
исходного файла» для трассировки `referenced_by`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Ключевые слова вида метаданного (источники запроса), uppercase → каноническая форма.
KIND_CANONICAL = {
    "СПРАВОЧНИК": "Справочник",
    "ДОКУМЕНТ": "Документ",
    "РЕГИСТРСВЕДЕНИЙ": "РегистрСведений",
    "РЕГИСТРНАКОПЛЕНИЯ": "РегистрНакопления",
    "РЕГИСТРБУХГАЛТЕРИИ": "РегистрБухгалтерии",
    "РЕГИСТРРАСЧЕТА": "РегистрРасчета",
    "ПЛАНВИДОВХАРАКТЕРИСТИК": "ПланВидовХарактеристик",
    "ПЛАНВИДОВРАСЧЕТА": "ПланВидовРасчета",
}

# Разделы запроса, завершающие список источников после `ИЗ`.
_SECTION_KW = {
    "ВЫБРАТЬ", "ГДЕ", "СГРУППИРОВАТЬ", "УПОРЯДОЧИТЬ", "ОБЪЕДИНИТЬ", "ИТОГИ",
    "ПОМЕСТИТЬ", "ИМЕЮЩИЕ", "ИНДЕКСИРОВАТЬ", "ДЛЯ", "РАЗРЕШЕННЫЕ", "ПЕРВЫЕ",
}
_JOIN_PRE = {"ЛЕВОЕ", "ПРАВОЕ", "ПОЛНОЕ", "ВНУТРЕННЕЕ", "ВНЕШНЕЕ"}
# Слова, которые не могут быть неявным псевдонимом источника.
_STOP_WORDS = _SECTION_KW | _JOIN_PRE | {"СОЕДИНЕНИЕ", "ПО", "КАК"}

_TOKEN_RE = re.compile(r"&?[^\W\d]\w*|[(),.;]", re.UNICODE)


@dataclass(frozen=True)
class SourceRef:
    """Источник запроса: вид, имя и (опционально) суффикс виртуальной/табличной таблицы."""

    kind: str
    name: str
    suffix: str | None
    line: int


@dataclass(frozen=True)
class _Tok:
    text: str
    start: int
    special: str | None

    @property
    def is_name(self) -> bool:
        return self.special is None

    @property
    def is_param(self) -> bool:
        return self.special is None and self.text.startswith("&")

    @property
    def up(self) -> str:
        return self.text.upper() if self.special is None else ""


def unwrap_query_text(bsl: str) -> tuple[str, list[int]]:
    """Развернуть строковую обвязку запроса.

    Возвращает (текст, карта_строк), где карта_строк[i] — номер строки исходного
    файла (1-based) для символа текста с индексом i.
    """
    out: list[str] = []
    lines: list[int] = []
    in_string = False
    for lineno, line in enumerate(bsl.split("\n"), 1):
        length = len(line)
        k = 0
        if in_string:
            # Строка-продолжение: снять ведущие пробелы и один префикс `|`.
            m = 0
            while m < length and line[m] in " \t":
                m += 1
            k = m + 1 if (m < length and line[m] == "|") else m
        while k < length:
            ch = line[k]
            if in_string:
                if ch == '"':
                    if k + 1 < length and line[k + 1] == '"':
                        out.append('"')
                        lines.append(lineno)
                        k += 2
                        continue
                    in_string = False
                    k += 1
                    continue
                out.append(ch)
                lines.append(lineno)
                k += 1
            else:
                if ch == '"':
                    in_string = True
                    k += 1
                elif ch == "/" and k + 1 < length and line[k + 1] == "/":
                    break  # строчный комментарий вне строки — пропустить остаток строки
                else:
                    k += 1
        if in_string:
            # Перенос внутри многострочного литерала — разделитель токенов.
            out.append("\n")
            lines.append(lineno)
    return "".join(out), lines


def _tokenize(text: str) -> list[_Tok]:
    toks: list[_Tok] = []
    for m in _TOKEN_RE.finditer(text):
        g = m.group()
        toks.append(_Tok(g, m.start(), g if g in "(),.;" else None))
    return toks


def _read_source(toks: list[_Tok], i: int, refs: list[SourceRef], line_map: list[int]) -> int:
    """Прочитать точечное имя источника с позиции i; добавить SourceRef при совпадении вида."""
    n = len(toks)
    if i >= n or not toks[i].is_name:
        return i
    parts = [toks[i]]
    j = i + 1
    while j + 1 < n and toks[j].special == "." and toks[j + 1].is_name:
        parts.append(toks[j + 1])
        j += 2
    first = parts[0]
    if first.is_param:
        return j
    kind = KIND_CANONICAL.get(first.up)
    if kind and len(parts) >= 2:
        suffix = parts[2].text if len(parts) >= 3 else None
        line = line_map[first.start] if first.start < len(line_map) else 1
        refs.append(SourceRef(kind=kind, name=parts[1].text, suffix=suffix, line=line))
    return j


def _read_from_list(toks: list[_Tok], i: int, refs: list[SourceRef], line_map: list[int]) -> int:
    """Прочитать список источников после `ИЗ` (через запятую) до раздела/соединения."""
    n = len(toks)
    while i < n:
        t = toks[i]
        if t.special == "(":  # подзапрос — внутренний `ИЗ` поймает верхний проход
            return i
        if not t.is_name or t.up in _STOP_WORDS:
            return i
        j = _read_source(toks, i, refs, line_map)
        if j == i:
            return i
        i = j
        # Снять псевдоним (явный `КАК x` или неявный `x`).
        if i < n and toks[i].up == "КАК":
            i += 1
            if i < n and toks[i].is_name:
                i += 1
        elif i < n and toks[i].is_name and toks[i].up not in _STOP_WORDS \
                and toks[i].up not in KIND_CANONICAL and not toks[i].is_param:
            i += 1
        if i < n and toks[i].special == ",":
            i += 1
            continue
        return i
    return i


def scan_module(bsl: str) -> list[SourceRef]:
    """Извлечь источники из текста модуля BSL."""
    text, line_map = unwrap_query_text(bsl)
    toks = _tokenize(text)
    refs: list[SourceRef] = []
    n = len(toks)
    i = 0
    while i < n:
        up = toks[i].up
        if up == "ИЗ":
            i = _read_from_list(toks, i + 1, refs, line_map)
        elif up == "СОЕДИНЕНИЕ":
            i = _read_source(toks, i + 1, refs, line_map)
        else:
            i += 1
    return refs
