"""Build, load, validate, and resolve task-local reference catalogs."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from pydantic import ValidationError

from review_tasks.infrastructure.text_files import write_text_lf

from .models import DevStandardReference, ReferenceCatalog


CATALOG_RELATIVE_PATH = Path("_review_info") / "reference-catalog.json"
ID_RE = re.compile(r"^(?:std|rdv)[1-9][0-9]*$")
HEADING_RE = re.compile(r"^###\s+((?:std|rdv)[1-9][0-9]*)\s*:\s*(\S.*?)\s*$")


class ReferenceCatalogError(ValueError):
    """Reference catalog violates its generated task contract."""


def _front_matter_description(path: Path, text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ReferenceCatalogError(f"{path}: отсутствует начальный front matter description")
    try:
        closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ReferenceCatalogError(f"{path}: не закрыт front matter") from exc
    try:
        metadata = yaml.safe_load("\n".join(lines[1:closing]))
    except yaml.YAMLError as exc:
        raise ReferenceCatalogError(f"{path}: некорректный front matter: {exc}") from exc
    description = metadata.get("description") if isinstance(metadata, dict) else None
    if not isinstance(description, str) or not description.strip():
        raise ReferenceCatalogError(f"{path}: отсутствует непустой front matter description")
    return description.strip()


def _card_ids(path: Path, text: str) -> list[str]:
    ids: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^###(?:\s|$)", line) is None:
            continue
        match = HEADING_RE.fullmatch(line)
        if match is None:
            raise ReferenceCatalogError(f"{path}:{line_number}: некорректный ID карточки")
        identifier = match.group(1)
        if identifier in ids:
            raise ReferenceCatalogError(f"{path}:{line_number}: повтор ID `{identifier}`")
        ids.append(identifier)
    if not ids:
        raise ReferenceCatalogError(f"{path}: отсутствуют карточки stdN/rdvN")
    return ids


def build_reference_catalog(dev_standards_dir: Path) -> ReferenceCatalog:
    if not dev_standards_dir.is_dir():
        raise ReferenceCatalogError(f"Каталог локальных карточек не найден: {dev_standards_dir}")
    task_root = dev_standards_dir.parent
    entries: list[DevStandardReference] = []
    seen_ids: dict[str, str] = {}
    for path in sorted(dev_standards_dir.rglob("*.md"), key=lambda item: item.relative_to(task_root).as_posix()):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ReferenceCatalogError(f"{path}: не удалось прочитать UTF-8: {exc}") from exc
        relative_path = path.relative_to(task_root).as_posix()
        description = _front_matter_description(path, text)
        ids = _card_ids(path, text)
        for identifier in ids:
            previous = seen_ids.get(identifier)
            if previous is not None:
                raise ReferenceCatalogError(
                    f"Повтор ID `{identifier}` в `{previous}` и `{relative_path}`"
                )
            seen_ids[identifier] = relative_path
        entries.append(
            DevStandardReference(path=relative_path, description=description, ids=ids)
        )
    return ReferenceCatalog(schema_version=1, dev_standards=entries)


def write_reference_catalog(task_root: Path) -> Path:
    catalog = build_reference_catalog(task_root / "dev-standarts")
    output = task_root / CATALOG_RELATIVE_PATH
    payload = json.dumps(
        catalog.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    write_text_lf(output, payload)
    return output


def _canonical_catalog_path(value: str) -> PurePosixPath:
    if "\\" in value:
        raise ReferenceCatalogError(f"Неканонический path в reference catalog: `{value}`")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or not path.parts:
        raise ReferenceCatalogError(f"Неканонический path в reference catalog: `{value}`")
    if path.parts[0] != "dev-standarts" or any(part in {"", ".", ".."} for part in path.parts):
        raise ReferenceCatalogError(f"Path выходит за `dev-standarts/`: `{value}`")
    return path


def _validate_loaded_catalog(catalog: ReferenceCatalog, task_root: Path) -> None:
    if catalog.schema_version != 1:
        raise ReferenceCatalogError(
            f"Неподдерживаемая schema_version reference catalog: {catalog.schema_version}"
        )
    standards_root = (task_root / "dev-standarts").resolve()
    seen_ids: dict[str, str] = {}
    for entry in catalog.dev_standards:
        canonical = _canonical_catalog_path(entry.path)
        resolved = (task_root / Path(*canonical.parts)).resolve()
        try:
            resolved.relative_to(standards_root)
        except ValueError as exc:
            raise ReferenceCatalogError(f"Path выходит за `dev-standarts/`: `{entry.path}`") from exc
        if not resolved.is_file():
            raise ReferenceCatalogError(f"Файл reference catalog не найден: `{entry.path}`")
        if not entry.description.strip():
            raise ReferenceCatalogError(f"Пустой description для `{entry.path}`")
        local_ids: set[str] = set()
        for identifier in entry.ids:
            if not ID_RE.fullmatch(identifier):
                raise ReferenceCatalogError(f"Некорректный ID `{identifier}` в `{entry.path}`")
            if identifier in local_ids or identifier in seen_ids:
                previous = seen_ids.get(identifier, entry.path)
                raise ReferenceCatalogError(
                    f"Повтор ID `{identifier}` в `{previous}` и `{entry.path}`"
                )
            local_ids.add(identifier)
            seen_ids[identifier] = entry.path


def load_reference_catalog(task_root: Path) -> ReferenceCatalog:
    path = task_root / CATALOG_RELATIVE_PATH
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceCatalogError(f"Не удалось прочитать reference catalog `{path}`: {exc}") from exc
    try:
        catalog = ReferenceCatalog.model_validate(raw)
    except ValidationError as exc:
        raise ReferenceCatalogError(f"Некорректная схема reference catalog `{path}`: {exc.errors()[0]['msg']}") from exc
    _validate_loaded_catalog(catalog, task_root)
    return catalog


def resolve_reference_id(identifier: str, *, task_root: Path | None = None) -> str:
    root = Path.cwd() if task_root is None else task_root
    if not ID_RE.fullmatch(identifier):
        raise ReferenceCatalogError(f"ID `{identifier}` должен иметь формат stdN или rdvN")
    catalog = load_reference_catalog(root)
    matches = [entry.path for entry in catalog.dev_standards if identifier in entry.ids]
    if len(matches) != 1:
        raise ReferenceCatalogError(f"Стандарт `{identifier}` не найден однозначно в reference catalog")
    return matches[0]
