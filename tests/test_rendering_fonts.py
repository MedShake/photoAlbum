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

    assert available

    family = available[0]

    assert resolve_font_family(family) == family


def test_resolve_unknown_font_uses_available_fallback():
    available = available_photo_album_fonts()

    assert DEFAULT_SANS_FONT in available

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


def test_bundled_fonts_render_text_without_system_font_configuration(tmp_path):
    """Exercise the empty font database seen with Windows Qt offscreen."""
    import os
    import subprocess
    import sys
    from xml.sax.saxutils import escape

    empty = tmp_path / "empty-fonts"
    empty.mkdir()
    config = tmp_path / "fonts.conf"
    config.write_text(
        f'<fontconfig><dir>{escape(empty.as_posix())}</dir>'
        f'<cachedir>{escape((tmp_path / "font-cache").as_posix())}</cachedir></fontconfig>',
        encoding="utf-8",
    )
    script = '''
from pathlib import Path
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QImage, QPainter, QPdfWriter
from PySide6.QtWidgets import QApplication
from pypdf import PdfReader
from photoalbum.rendering.fonts import (
    DEFAULT_SANS_FONT, DEFAULT_SERIF_FONT, DEFAULT_MONOSPACE_FONT,
    available_photo_album_fonts, resolve_font_family,
)
app = QApplication([])
if sys.platform.startswith("linux"):
    assert not {DEFAULT_SANS_FONT, DEFAULT_SERIF_FONT, DEFAULT_MONOSPACE_FONT}.intersection(QFontDatabase.families()), "Fontconfig isolation failed"
assert {DEFAULT_SANS_FONT, DEFAULT_SERIF_FONT, DEFAULT_MONOSPACE_FONT} <= set(available_photo_album_fonts())
font = QFont(resolve_font_family(None))
font.setPixelSize(24)
assert QFontInfo(font).family() == DEFAULT_SANS_FONT
image = QImage(240, 80, QImage.Format.Format_RGB32)
image.fill(Qt.GlobalColor.white)
painter = QPainter(image)
painter.setFont(font)
painter.drawText(5, 35, "Photo Album")
painter.end()
assert any(image.pixel(x, y) != 0xffffffff for x in range(240) for y in range(80))
output = Path(sys.argv[1])
writer = QPdfWriter(str(output))
painter = QPainter(writer)
painter.setFont(font)
painter.drawText(20, 50, "Photo Album")
painter.end()
del writer
assert "Photo Album" in " ".join(PdfReader(output).pages[0].extract_text().split())
'''
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "FONTCONFIG_FILE": str(config),
           "QT_QPA_FONTDIR": str(empty)}
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path / "fonts.pdf")],
                            env=env, capture_output=True, timeout=30)
    assert result.returncode == 0, (result.stdout + result.stderr).decode("utf-8", errors="replace")
