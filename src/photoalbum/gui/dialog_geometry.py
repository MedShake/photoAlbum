"""Size secondary dialogs to the usable screen without imposing a large minimum."""

from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog


def _available_geometry(dialog: QDialog) -> QRect | None:
    """Use the screen associated with this dialog (not necessarily primary)."""
    screen = dialog.screen() or QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else None


def fit_dialog_to_screen(
    dialog: QDialog,
    preferred_width: int,
    preferred_height: int,
    *,
    screen_fraction: float = 0.90,
) -> None:
    """Keep a dialog's usual size on large screens, shrink it on small ones.

    The actual available geometry excludes system panels/taskbars. Existing
    minimum sizes remain honoured when they fit on the screen. This helper
    only chooses the initial size; table/browser widgets manage overflow.
    """
    available = _available_geometry(dialog)
    if available is None:
        dialog.resize(preferred_width, preferred_height)
        return

    width_limit = max(1, min(available.width(), round(available.width() * screen_fraction)))
    height_limit = max(1, min(available.height(), round(available.height() * screen_fraction)))

    # An existing minimum may exceed the preferred fraction on a small
    # display. In that case, use the minimum if it still fits the screen.
    # Never request a dimension larger than the actual usable area.
    width = min(available.width(), max(dialog.minimumWidth(), min(preferred_width, width_limit)))
    height = min(available.height(), max(dialog.minimumHeight(), min(preferred_height, height_limit)))
    dialog.resize(max(1, width), max(1, height))
