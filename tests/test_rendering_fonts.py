from pathlib import Path

from PySide6.QtWidgets import QApplication

from photoalbum.rendering.fonts import (
    DEFAULT_MONOSPACE_FONT,
    DEFAULT_SANS_FONT,
    DEFAULT_SERIF_FONT,
    PHOTO_ALBUM_FONTS,
    available_photo_album_fonts,
    resolve_font_family,
)


# QFontDatabase requires a Qt application to exist.
_app = QApplication.instance() or QApplication([])


def test_default_fonts_belong_to_declared_palette():
    assert DEFAULT_SANS_FONT in PHOTO_ALBUM_FONTS
    assert DEFAULT_SERIF_FONT in PHOTO_ALBUM_FONTS
    assert DEFAULT_MONOSPACE_FONT in PHOTO_ALBUM_FONTS


def test_available_fonts_are_from_declared_palette():
    available = available_photo_album_fonts()

    assert all(
        family in PHOTO_ALBUM_FONTS
        for family in available
    )


def test_resolve_available_font_family():
    available = available_photo_album_fonts()

    if not available:
        return

    family = available[0]

    assert resolve_font_family(family) == family


def test_resolve_unknown_font_uses_available_fallback():
    available = available_photo_album_fonts()

    if DEFAULT_SANS_FONT not in available:
        return

    assert (
        resolve_font_family(
            "__photo_album_missing_font__"
        )
        == DEFAULT_SANS_FONT
    )


def test_templates_do_not_hardcode_legacy_font_families():
    templates = (
        Path(__file__).parents[1]
        / "src"
        / "photoalbum"
        / "templates"
    )

    forbidden = (
        '"Arial"',
        '"Courier"',
        '"Times"',
        '"Helvetica"',
        "'Arial'",
        "'Courier'",
        "'Times'",
        "'Helvetica'",
    )

    violations = []

    for source in templates.rglob("*.py"):
        text = source.read_text(
            encoding="utf-8"
        )

        for value in forbidden:
            if value in text:
                violations.append(
                    f"{source}: {value}"
                )

    assert not violations, (
        "Hard-coded legacy font families found:\n"
        + "\n".join(violations)
    )


def test_font_palette_is_reused_and_invalidated_when_qt_fonts_change(monkeypatch):
    from unittest.mock import Mock
    from photoalbum.rendering import fonts

    families = Mock(return_value=[DEFAULT_SANS_FONT])
    monkeypatch.setattr(fonts.QFontDatabase, "families", families)
    fonts._invalidate_font_palette()
    try:
        assert available_photo_album_fonts() == (DEFAULT_SANS_FONT,)
        for _ in range(5):
            assert resolve_font_family(DEFAULT_SANS_FONT) == DEFAULT_SANS_FONT
        assert families.call_count == 1
        families.return_value = [DEFAULT_SERIF_FONT]
        _app.fontDatabaseChanged.emit()
        assert available_photo_album_fonts() == (DEFAULT_SERIF_FONT,)
        assert families.call_count == 2
    finally:
        fonts._invalidate_font_palette()
