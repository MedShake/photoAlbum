from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

from PySide6.QtGui import QIcon


@lru_cache(maxsize=None)
def resource_icon(filename: str) -> QIcon:
    """Return a cached SVG icon bundled with the application."""
    path = files("photoalbum.resources").joinpath("icons", filename)
    return QIcon(str(path))
