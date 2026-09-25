"""Task-local, atomic storage for the machine-owned Stage 1 result."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from review_tasks.sgr_schema import ReviewStage1Result, ReviewYamlError, translate_validation_error


STAGE1_NAME = "review_result_stage1.yaml"
STAGE2_NAME = "review_result_stage2.yaml"
LINE_MAP_NAME = "review_lines.json"
_CANDIDATE_RE = re.compile(r"^candidate-([1-9][0-9]*)$")


def normalize_area(value: str) -> str:
    return value.strip().casefold()


def normalize_candidate_file(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized


def normalize_line_map_file(value: str) -> str:
    return normalize_candidate_file(value).casefold()


def normalize_observation(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_bsp_module(value: str) -> str:
    normalized = value.strip()
    if not normalized or not normalized.isidentifier():
        raise _error("`--module` должен содержать конкретное имя общего модуля БСП без пути или имени метода.")
    return normalized


def review_info_from_cwd(cwd: Path | None = None) -> Path:
    root = Path.cwd() if cwd is None else cwd
    return root / "_review_info"


def stage1_path(cwd: Path | None = None) -> Path:
    return review_info_from_cwd(cwd) / STAGE1_NAME


def line_map_path(cwd: Path | None = None) -> Path:
    return review_info_from_cwd(cwd) / LINE_MAP_NAME


def _error(message: str) -> ReviewYamlError:
    return ReviewYamlError(message)


def load_line_bounds(cwd: Path | None = None) -> dict[str, tuple[int, int]]:
    path = line_map_path(cwd)
    if not path.is_file():
        raise _error(f"Не найдена обязательная карта границ строк: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _error(f"{path}: не удалось прочитать review_lines.json: {exc}") from exc
    if not isinstance(raw, dict):
        raise _error(f"{path}: review_lines.json должен быть объектом {{file: [min_line, max_line]}}")
    result: dict[str, tuple[int, int]] = {}
    for file, bounds in raw.items():
        if not isinstance(file, str) or not isinstance(bounds, list) or len(bounds) != 2:
            raise _error(f"{path}: неверная запись карты границ для `{file}`")
        low, high = bounds
        if isinstance(low, bool) or isinstance(high, bool) or not isinstance(low, int) or not isinstance(high, int) or low <= 0 or high <= 0 or low > high:
            raise _error(f"{path}: границы `{file}` должны быть положительной упорядоченной парой [min_line, max_line]")
        key = normalize_line_map_file(file)
        if key in result:
            raise _error(f"{path}: дублирующийся путь после нормализации: `{file}`")
        result[key] = (low, high)
    return result


def validate_candidate_bounds(parsed: ReviewStage1Result, cwd: Path | None = None) -> None:
    bounds = load_line_bounds(cwd)
    for candidate in parsed.risk_candidates.items:
        normalized = normalize_line_map_file(candidate.file)
        allowed = bounds.get(normalized)
        if allowed is None:
            raise _error(f"candidate `{candidate.name}`: файл `{candidate.file}` отсутствует в review_lines.json")
        low, high = allowed
        if candidate.start_line < low or candidate.end_line > high:
            raise _error(
                f"candidate `{candidate.name}`: строки {candidate.start_line}-{candidate.end_line} файла "
                f"`{candidate.file}` вне допустимого диапазона {low}-{high}; исправьте только start_line/end_line."
            )


def parse_stage1_mapping(raw: Any, *, source: str, cwd: Path | None = None) -> ReviewStage1Result:
    if not isinstance(raw, dict):
        raise _error(f"{source}: YAML должен быть объектом верхнего уровня.")
    try:
        parsed = ReviewStage1Result.model_validate(raw)
    except ValidationError as exc:
        raise translate_validation_error(exc, source=source) from exc
    validate_candidate_bounds(parsed, cwd)
    return parsed


def load_stage1(*, cwd: Path | None = None, required: bool = True) -> ReviewStage1Result:
    path = stage1_path(cwd)
    if not path.is_file():
        if required:
            raise _error(f"Не найден обязательный Stage 1 результат: {path}")
        return ReviewStage1Result.model_validate({"risk_candidates": {"items": []}})
    text = path.read_text(encoding="utf-8")
    if "```" in text:
        raise _error(f"{path}: Stage 1 должен быть bare YAML без Markdown-обёртки.")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise _error(f"{path}: YAML не разбирается: {exc}") from exc
    return parse_stage1_mapping(raw, source=str(path), cwd=cwd)


def stage1_mapping(parsed: ReviewStage1Result) -> dict[str, Any]:
    return parsed.model_dump(mode="python")


def _write_atomic(path: Path, data: dict[str, Any]) -> None:
    payload = yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000
    ).replace("\r\n", "\n")
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def save_stage1(parsed: ReviewStage1Result, *, cwd: Path | None = None) -> None:
    path = stage1_path(cwd)
    if not path.parent.is_dir():
        raise _error(f"Не найден каталог _review_info: {path.parent}")
    _write_atomic(path, stage1_mapping(parsed))


def _candidate_key(candidate: Any) -> tuple[str, str, int, int, str]:
    return (
        normalize_area(candidate.area),
        normalize_candidate_file(candidate.file),
        candidate.start_line,
        candidate.end_line,
        normalize_observation(candidate.observation),
    )


def _validate_names(parsed: ReviewStage1Result) -> int:
    numbers: list[int] = []
    seen: set[str] = set()
    for candidate in parsed.risk_candidates.items:
        if candidate.name in seen:
            raise _error(f"Stage 1 содержит повторное имя candidate `{candidate.name}`")
        seen.add(candidate.name)
        match = _CANDIDATE_RE.fullmatch(candidate.name)
        if match is None:
            raise _error(f"Stage 1 содержит неверное имя candidate `{candidate.name}`")
        numbers.append(int(match.group(1)))
    return max(numbers, default=0)


def add_candidate(*, area: str, file: str, start_line: int, end_line: int, observation: str, cwd: Path | None = None) -> tuple[str, bool]:
    if not area.strip() or not file.strip() or not observation.strip():
        field = "area" if not area.strip() else "file" if not file.strip() else "observation"
        raise _error(f"Поле `{field}` не может быть пустым.")
    if start_line <= 0 or end_line <= 0:
        raise _error("start_line и end_line должны быть положительными целыми числами.")
    if start_line > end_line:
        raise _error("start_line не может быть больше end_line.")
    bounds = load_line_bounds(cwd)
    normalized_file = normalize_candidate_file(file)
    allowed = bounds.get(normalize_line_map_file(file))
    if allowed is None:
        raise _error(f"Файл `{file}` отсутствует в review_lines.json.")
    if start_line < allowed[0] or end_line > allowed[1]:
        raise _error(f"Строки {start_line}-{end_line} файла `{file}` вне допустимого диапазона {allowed[0]}-{allowed[1]}.")
    parsed = load_stage1(cwd=cwd, required=False)
    maximum = _validate_names(parsed)
    requested = (normalize_area(area), normalized_file, start_line, end_line, normalize_observation(observation))
    for candidate in parsed.risk_candidates.items:
        if _candidate_key(candidate) == requested:
            return candidate.name, False
    raw = stage1_mapping(parsed)
    raw["risk_candidates"]["items"].append({
        "name": f"candidate-{maximum + 1}", "area": normalize_area(area), "file": normalized_file,
        "start_line": start_line, "end_line": end_line, "observation": normalize_observation(observation),
        "standard_hints": {"dev_standard_ids": [], "platform_index_files": [], "bsp_files": []},
    })
    result = parse_stage1_mapping(raw, source=str(stage1_path(cwd)), cwd=cwd)
    save_stage1(result, cwd=cwd)
    return result.risk_candidates.items[-1].name, True


def remove_candidate(name: str, *, cwd: Path | None = None) -> bool:
    if _CANDIDATE_RE.fullmatch(name) is None:
        raise _error("`--candidate` должен иметь формат candidate-N.")
    if (review_info_from_cwd(cwd) / STAGE2_NAME).exists():
        raise _error("Stage 2 уже существует: сохраните candidate и добавьте/обновите его finding с self_check.decision: drop.")
    parsed = load_stage1(cwd=cwd)
    _validate_names(parsed)
    raw = stage1_mapping(parsed)
    items = raw["risk_candidates"]["items"]
    new_items = [item for item in items if item["name"] != name]
    if len(items) == len(new_items):
        return False
    raw["risk_candidates"]["items"] = new_items
    result = parse_stage1_mapping(raw, source=str(stage1_path(cwd)), cwd=cwd)
    save_stage1(result, cwd=cwd)
    return True


def list_candidates(*, cwd: Path | None = None) -> str:
    parsed = load_stage1(cwd=cwd)
    return yaml.safe_dump(
        [item.model_dump(mode="python") for item in parsed.risk_candidates.items],
        allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000,
    ).replace("\r\n", "\n")


def _find_candidate(parsed: ReviewStage1Result, name: str) -> int:
    if _CANDIDATE_RE.fullmatch(name) is None:
        raise _error("`--candidate` должен иметь формат candidate-N.")
    for index, candidate in enumerate(parsed.risk_candidates.items):
        if candidate.name == name:
            return index
    raise _error(f"Кандидат `{name}` не найден.")


def _safe_relative_file(value: str, *, root: str, cwd: Path | None) -> str:
    normalized = normalize_candidate_file(value)
    if not normalized.startswith(root) or ".." in normalized.split("/") or not normalized:
        raise _error(f"Файл должен быть существующим относительным путём внутри `{root}`.")
    path = (Path.cwd() if cwd is None else cwd) / normalized
    if not path.is_file():
        raise _error(f"Не найден файл `{normalized}`.")
    return normalized


def change_hint(*, candidate: str, field: str, value: str, add: bool, cwd: Path | None = None) -> bool:
    parsed = load_stage1(cwd=cwd)
    _validate_names(parsed)
    index = _find_candidate(parsed, candidate)
    raw = stage1_mapping(parsed)
    values = raw["risk_candidates"]["items"][index]["standard_hints"][field]
    if add:
        if value in values:
            return False
        values.append(value)
    else:
        if value not in values:
            return False
        values.remove(value)
    result = parse_stage1_mapping(raw, source=str(stage1_path(cwd)), cwd=cwd)
    save_stage1(result, cwd=cwd)
    return True

