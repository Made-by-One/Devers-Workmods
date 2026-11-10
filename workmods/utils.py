"""Small OS helpers that do not belong to a specific layer."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_folder(path: str | Path | None) -> bool:
    """Open ``path`` in the platform file manager. Returns False on failure."""
    if not path:
        return False
    target = str(Path(path).expanduser())
    if not Path(target).exists():
        return False
    try:
        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
        return True
    except OSError:
        return False


__all__ = ["open_folder"]
