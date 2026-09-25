from __future__ import annotations

from .base import IdeAdapter, IdeAdapterError
from .codex import CodexAdapter
from .cursor import CursorAdapter
from .opencode import OpenCodeAdapter

_ADAPTERS: dict[str, IdeAdapter] = {
    CursorAdapter.name: CursorAdapter(),
    CodexAdapter.name: CodexAdapter(),
    OpenCodeAdapter.name: OpenCodeAdapter(),
}

IDE_CHOICES = tuple(_ADAPTERS.keys())


def get_adapter(name: str) -> IdeAdapter:
    try:
        return _ADAPTERS[name]
    except KeyError as exc:
        raise IdeAdapterError(f"Неподдерживаемая IDE: {name}") from exc
