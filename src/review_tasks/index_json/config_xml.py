"""Резолв `configRoot` и чтение XML конфигурации 1С из git-ref.

XML читается напрямую из ревизии (`git show <target>:<path>`) и парсится в памяти —
на диск не сохраняется (в каталог задачи попадает только indexes.json). `configRoot`
(переменный префикс выгрузки в репозитории) вычисляется из путей изменённых BSL
обобщённо: первый сегмент пути, равный известному каталогу вида, — граница.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from ..infrastructure import git as gitproc
from .configurator_xml import parse_object as parse_configurator_object
from .edt_mdo import parse_object as parse_edt_object
from .model import ParsedObject

# Вид метаданного → каталог выгрузки конфигурации.
KIND_DIR = {
    "Справочник": "Catalogs",
    "Документ": "Documents",
    "РегистрСведений": "InformationRegisters",
    "РегистрНакопления": "AccumulationRegisters",
    "РегистрБухгалтерии": "AccountingRegisters",
    "РегистрРасчета": "CalculationRegisters",
    "ПланВидовХарактеристик": "ChartsOfCharacteristicTypes",
    "ПланВидовРасчета": "ChartsOfCalculationTypes",
    "КритерийОтбора": "FilterCriteria",
}
KNOWN_DIRS = frozenset(KIND_DIR.values())


def compute_config_root(bsl_paths: list[str]) -> str:
    """Вычислить общий `configRoot` по путям изменённых BSL.

    Покрывает `Ext/`-модули, формы (`Forms/.../Ext/Form/Module.bsl`) и команды
    (`Commands/.../Ext/CommandModule.bsl`) — граница всегда первый сегмент,
    совпадающий с известным каталогом вида.
    """
    roots: list[str] = []
    for raw in bsl_paths:
        segments = raw.replace("\\", "/").split("/")
        for idx, seg in enumerate(segments):
            if seg in KNOWN_DIRS:
                roots.append("/".join(segments[:idx]))
                break
    if not roots:
        return ""
    return Counter(roots).most_common(1)[0][0]


class GitConfigSource:
    """Доступ к blob'ам конфигурации в target-ref через git CLI (stdlib subprocess)."""

    def __init__(self, target: str, cwd: Path | None = None) -> None:
        self.target = target
        self.cwd = cwd
        self._tree: list[str] | None = None

    def _git(self, args: list[str]) -> subprocess.CompletedProcess:
        return gitproc.git_result(args, cwd=self.cwd)

    def exists(self, path: str) -> bool:
        result = self._git(["cat-file", "-e", f"{self.target}:{path}"])
        return result.returncode == 0

    def read(self, path: str) -> bytes:
        result = self._git(["show", f"{self.target}:{path}"])
        if result.returncode != 0:
            raise FileNotFoundError(f"{self.target}:{path}")
        return result.stdout

    def tree(self) -> list[str]:
        if self._tree is None:
            result = self._git(["ls-tree", "-r", "--name-only", self.target])
            text = result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else ""
            self._tree = [line for line in text.split("\n") if line.strip()]
        return self._tree

    def _ls_dir(self, path: str) -> list[str]:
        """Имена непосредственных дочерних записей дерева `<target>:<path>/` (один уровень).

        В отличие от `tree()` (рекурсивный листинг всего дерева ревизии — дорог на
        больших конфигурациях), читает только один каталог. Возвращает полные пути
        от корня репозитория; несуществующий каталог даёт пустой список.
        """
        spec = path if path.endswith("/") else path + "/"
        result = self._git(["ls-tree", "--name-only", self.target, spec])
        if result.returncode != 0:
            return []
        text = result.stdout.decode("utf-8", errors="replace")
        return [line for line in text.split("\n") if line.strip()]

    def _resolve_path(self, config_root: str, rel: str) -> str | None:
        direct = f"{config_root}/{rel}" if config_root else rel
        if self.exists(direct):
            return direct
        # Идентификаторы 1С регистронезависимы: имя объекта в запросе может
        # отличаться регистром от имени XML-файла. Ищем по суффиксу без учёта
        # регистра и возвращаем канонический путь из дерева ревизии.
        rel_lower = rel.lower()
        suffix_lower = ("/" + rel).lower()
        candidates = [
            t for t in self.tree()
            if t.lower() == rel_lower or t.lower().endswith(suffix_lower)
        ]
        if config_root:
            root_lower = (config_root + "/").lower()
            preferred = [c for c in candidates if c.lower().startswith(root_lower)]
            if preferred:
                candidates = preferred
        return sorted(candidates)[0] if candidates else None

    def load_object(self, config_root: str, kind: str, name: str) -> ET.Element | None:
        """Прочитать и распарсить XML объекта; вернуть корневой элемент или None."""
        directory = KIND_DIR.get(kind)
        if not directory:
            return None
        path = self._resolve_path(config_root, f"{directory}/{name}.xml")
        if path is None:
            return None
        return self._parse(path)

    def load_parsed_object(self, config_root: str, kind: str, name: str) -> ParsedObject | None:
        """Вернуть общую модель XML Конфигуратора либо полного EDT MDO.

        XML проверяется первым для полной обратной совместимости. Исключение
        ``UnsupportedEdtDelta`` намеренно передаётся вызывающему коду: только он
        знает ссылку из BSL и может вывести понятную диагностику.
        """
        directory = KIND_DIR.get(kind)
        if not directory:
            return None
        xml_path = self._resolve_path(config_root, f"{directory}/{name}.xml")
        if xml_path is not None:
            return parse_configurator_object(kind, self._parse(xml_path))
        mdo_path = self._resolve_path(config_root, f"{directory}/{name}/{name}.mdo")
        if mdo_path is None:
            return None
        return parse_edt_object(kind, self._parse(mdo_path))

    def list_xml(self, config_root: str, directory: str) -> list[str]:
        """Пути всех XML непосредственно внутри каталога вида под `configRoot`.

        Листает только сам каталог (`_ls_dir`), а не всё дерево ревизии — этого
        достаточно для FilterCriteria (объект — `<dir>/<Имя>.xml`, вложенные
        `<dir>/<Имя>/...` не нужны и не возвращаются нерекурсивным листингом).
        """
        base = f"{config_root}/{directory}" if config_root else directory
        return sorted(t for t in self._ls_dir(base) if t.endswith(".xml"))

    def list_mdo(self, config_root: str, directory: str) -> list[str]:
        """Вернуть EDT MDO `<dir>/<Имя>/<Имя>.mdo` из уже кэшированного дерева."""
        prefix = f"{config_root}/{directory}".strip("/") if config_root else directory
        prefix_parts = prefix.lower().split("/")
        result: list[str] = []
        for path in self.tree():
            parts = path.split("/")
            if [item.lower() for item in parts[:len(prefix_parts)]] != prefix_parts:
                continue
            tail = parts[len(prefix_parts):]
            if len(tail) == 2 and tail[1].lower().endswith(".mdo") and tail[0].lower() == tail[1][:-4].lower():
                result.append(path)
        return sorted(result)

    def _parse(self, path: str) -> ET.Element | None:
        try:
            data = self.read(path)
            return ET.fromstring(data)
        except (FileNotFoundError, ET.ParseError):
            return None
