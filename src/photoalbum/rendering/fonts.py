from __future__ import annotations

from PySide6.QtGui import QFontDatabase, QGuiApplication


DEFAULT_SANS_FONT = "DejaVu Sans"
DEFAULT_SERIF_FONT = "DejaVu Serif"
DEFAULT_MONOSPACE_FONT = "DejaVu Sans Mono"


PHOTO_ALBUM_FONTS = (
    "DejaVu Sans",
    "DejaVu Serif",
    "DejaVu Sans Mono",
    "Liberation Sans",
    "Liberation Serif",
    "Liberation Mono",
)

_font_palette: tuple[str, ...] | None = None
_font_application: QGuiApplication | None = None


def _invalidate_font_palette() -> None:
    global _font_palette
    _font_palette = None


def available_photo_album_fonts() -> tuple[str, ...]:
    """
    Return the Photo Album font palette that is actually
    available to Qt on the current system.
    """
    global _font_palette, _font_application
    application = QGuiApplication.instance()
    if application is not _font_application:
        _font_application = application
        _invalidate_font_palette()
        if application is not None:
            application.fontDatabaseChanged.connect(_invalidate_font_palette)

    if _font_palette is None:
        installed = set(QFontDatabase.families())
        _font_palette = tuple(family for family in PHOTO_ALBUM_FONTS if family in installed)
    return _font_palette


def resolve_font_family(
    requested: str | None,
    *,
    fallback: str = DEFAULT_SANS_FONT,
) -> str:
    """
    Resolve a requested font against the controlled
    Photo Album palette.

    Never silently accept an arbitrary system font.
    """
    available = available_photo_album_fonts()

    if requested in available:
        return requested

    if fallback in available:
        return fallback

    if available:
        return available[0]

    # Last-resort Qt generic family.
    return "Sans Serif"
