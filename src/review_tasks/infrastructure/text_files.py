"""Единый модуль текстового I/O review-tasks (D7).

Единственные реализации BOM-снимающего чтения и LF-нормализованной записи:

- `read_text_safe(path)` — вернуть текст файла (UTF-8 с BOM-снятием и
  fallback-decode `errors="replace"`); отсутствующий файл → пустая строка;
- `read_text_required(path)` — то же, но отсутствующий файл → `FileNotFoundError`;
- `write_text_lf(path, content)` — записать UTF-8 без BOM с LF EOL, создавая
  родительские каталоги.

Потребители: `cli.py`, `adapters/base.py`, `mcp_registry.py`,
`index_json/build.py`, `config.py` и `adapters/codex.py` (TOML-чтение). Обёртки
доменных ошибок (`ConfigError`/`IdeAdapterError`) остаются в вызывающих модулях.
"""

from __future__ import annotations

from pathlib import Path


def _decode_bom(data: bytes) -> str:
    # utf-8 с фолбэком; BSL и конфиги в проекте — utf-8, BOM снимается.
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def read_text_safe(path: Path) -> str:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return ""
    return _decode_bom(data)


def read_text_required(path: Path) -> str:
    return _decode_bom(path.read_bytes())


def write_text_lf(path: Path, content: str) -> None:
    """Записать UTF-8 без BOM c LF EOL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    path.write_bytes(normalized.encode("utf-8"))
