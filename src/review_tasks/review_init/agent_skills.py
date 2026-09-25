"""IDE-neutral projection of repo-local Agent Skills and MCP registry snapshots."""

from __future__ import annotations

from pathlib import Path

from review_tasks.infrastructure.text_files import read_text_required, write_text_lf
from review_tasks.integrations.mcp_registry import IdeAdapterError, load_mcp_registry


class SkillProjectionError(ValueError):
    """Common Agent Skills projection cannot satisfy its generated layout contract."""


def _copy_required_text(src: Path, dst: Path) -> None:
    write_text_lf(dst, read_text_required(src))


def _iter_skill_template_files(skill_dir: Path) -> tuple[Path, ...]:
    ignored_suffixes = {".pyc", ".pyo"}
    return tuple(
        path
        for path in skill_dir.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.lower() not in ignored_suffixes
    )


def _copy_skill_template(skill_dir: Path, skills_root: Path) -> None:
    if not (skill_dir / "SKILL.md").is_file():
        return
    destination = skills_root / skill_dir.name
    for path in sorted(_iter_skill_template_files(skill_dir)):
        _copy_required_text(path, destination / path.relative_to(skill_dir))


def _copy_task_skills(templates_dir: Path, skills_root: Path) -> None:
    skills_dir = templates_dir / "task" / "skills"
    if not skills_dir.is_dir():
        raise SkillProjectionError(
            f"Каталог task skills не найден: {skills_dir}"
        )
    for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
        _copy_skill_template(skill_dir, skills_root)


def _select_task_dirs(task_dirs: tuple[Path, ...]) -> tuple[Path, ...]:
    unique = sorted({path.resolve() for path in task_dirs}, key=lambda path: str(path))
    for path in unique:
        if not path.is_dir():
            raise SkillProjectionError(f"Каталог task capsule не найден: {path}")
        if not (path / "AGENTS.md").is_file():
            raise SkillProjectionError(f"AGENTS.md task capsule не найден: {path}")
        if not (path / "_review_info" / "meta.txt").is_file():
            raise SkillProjectionError(f"meta.txt task capsule не найден: {path}")
    return tuple(unique)


def _copy_mcp_registry_to(templates_dir: Path, destination_root: Path) -> None:
    src = templates_dir / "task" / "mcp" / "registry.json"
    try:
        load_mcp_registry(src)
    except IdeAdapterError as exc:
        raise SkillProjectionError(str(exc)) from exc
    dst = destination_root / ".review-tasks" / "mcp" / "registry.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def project_agent_skills(
    reviews_root: Path,
    templates_dir: Path,
    *,
    task_dirs: tuple[Path, ...],
    mcp_mode: str = "required",
) -> tuple[Path, ...]:
    """Project task-local skills and registry snapshots independently of the IDE."""
    selected_task_dirs = _select_task_dirs(task_dirs)

    for task_dir in selected_task_dirs:
        _copy_task_skills(templates_dir, task_dir / ".agents" / "skills")
        _copy_mcp_registry_to(templates_dir, task_dir)
        meta = task_dir / "_review_info" / "meta.txt"
        lines = [line for line in read_text_required(meta).splitlines() if not line.startswith("mcp_mode:")]
        write_text_lf(meta, "\n".join([*lines, f"mcp_mode: {mcp_mode}"]) + "\n")

    return selected_task_dirs
