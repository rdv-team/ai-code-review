from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_text_file(path: Path) -> None:
    """Open a text file with the operating system's registered handler."""
    native_path = str(path)
    if sys.platform == "win32":
        startfile = getattr(os, "startfile", None)
        if startfile is None:
            raise OSError("The Windows registered file handler is unavailable.")
        startfile(native_path)
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", native_path], close_fds=True)
        return
    if sys.platform.startswith("linux"):
        subprocess.Popen(["xdg-open", native_path], close_fds=True)
        return
    raise OSError(f"Opening text files is unsupported on platform {sys.platform!r}.")
