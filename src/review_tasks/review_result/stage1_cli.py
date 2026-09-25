"""Console entry points for narrow Stage 1 commands."""

from __future__ import annotations

import argparse
import sys

from review_tasks.reference_catalog import ReferenceCatalogError, resolve_reference_id
from review_tasks.sgr_schema import ReviewYamlError
from review_tasks.review_result.stage1_storage import (
    _safe_relative_file,
    add_candidate,
    change_hint,
    list_candidates,
    normalize_bsp_module,
    remove_candidate,
)


class _RussianParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"Ошибка аргументов: {message}. Пример вызова приведён в --help.\n")


def _run(parser: argparse.ArgumentParser, argv: list[str] | None, action) -> int:
    try:
        args = parser.parse_args(argv)
        return action(args)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 1
    except ReviewYamlError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def add_main(argv: list[str] | None = None) -> int:
    parser = _RussianParser(prog="review-tasks stage1-add-candidate", description="Добавить кандидата Stage 1.", allow_abbrev=False)
    for flag, typ in (("--area", str), ("--file", str), ("--start-line", int), ("--end-line", int), ("--observation", str)):
        parser.add_argument(flag, required=True, type=typ)
    def action(args):
        name, _created = add_candidate(area=args.area, file=args.file, start_line=args.start_line, end_line=args.end_line, observation=args.observation)
        print(name)
        return 0
    return _run(parser, argv, action)


def remove_main(argv: list[str] | None = None) -> int:
    parser = _RussianParser(prog="review-tasks stage1-remove-candidate", description="Удалить кандидата до Stage 2.", allow_abbrev=False)
    parser.add_argument("--candidate", required=True)
    return _run(parser, argv, lambda args: (remove_candidate(args.candidate), 0)[1])


def list_main(argv: list[str] | None = None) -> int:
    parser = _RussianParser(prog="review-tasks stage1-list-candidates", description="Вывести кандидаты Stage 1.", allow_abbrev=False)
    return _run(parser, argv, lambda args: (sys.stdout.write(list_candidates()), 0)[1])


def _hint_main(argv, *, command: str, field: str, kind: str, add: bool) -> int:
    # Deliberate contract: candidate-specific link/unlink commands replace a
    # broad stage1-add-standards command. Dev standards persist only their
    # canonical ID; file/title are resolved data used for validation/output.
    parser = _RussianParser(prog=f"review-tasks {command}", description=("Добавить" if add else "Удалить") + " привязку кандидата.", allow_abbrev=False)
    parser.add_argument("--candidate", required=True)
    flag = {"dev": "--id", "platform": "--file", "bsp": "--module"}[kind]
    parser.add_argument(flag, required=True)
    def action(args):
        value = getattr(args, flag[2:].replace("-", "_"))
        resolved_file = None
        if kind == "dev":
            try:
                resolved_file = resolve_reference_id(value)
            except ReferenceCatalogError as exc:
                raise ReviewYamlError(str(exc)) from exc
        elif kind == "platform":
            value = _safe_relative_file(value, root="platform-database-indexes/", cwd=None)
        else:
            value = normalize_bsp_module(value)
        changed = change_hint(candidate=args.candidate, field=field, value=value, add=add)
        if resolved_file is not None and add and changed:
            print(f"{value}: {resolved_file}")
        return 0
    return _run(parser, argv, action)


def link_dev_main(argv=None): return _hint_main(argv, command="stage1-link-dev-standard", field="dev_standard_ids", kind="dev", add=True)
def unlink_dev_main(argv=None): return _hint_main(argv, command="stage1-unlink-dev-standard", field="dev_standard_ids", kind="dev", add=False)
def link_platform_main(argv=None): return _hint_main(argv, command="stage1-link-platform-index", field="platform_index_files", kind="platform", add=True)
def unlink_platform_main(argv=None): return _hint_main(argv, command="stage1-unlink-platform-index", field="platform_index_files", kind="platform", add=False)
def link_bsp_main(argv=None): return _hint_main(argv, command="stage1-link-bsp-file", field="bsp_files", kind="bsp", add=True)
def unlink_bsp_main(argv=None): return _hint_main(argv, command="stage1-unlink-bsp-file", field="bsp_files", kind="bsp", add=False)
