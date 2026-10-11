"""The accordion heading must behave and paint consistently across Qt styles."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyleFactory, QWidget

from photoalbum.gui.widgets.accordion_section import AccordionSection


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("style", ["Fusion", "Windows"])
def test_header_is_full_width_and_keyboard_accessible(app, style):
    available = QStyleFactory.keys()
    if style not in available:
        pytest.skip(f"Qt style {style} not available on this platform")
    original = app.style().objectName()
    try:
        app.setStyle(style)
        section = AccordionSection("Format", QWidget())
        section.resize(640, 75)
        section.set_summary("A4 — portrait")
        section.show()
        app.processEvents()
        heading = section._heading
        assert heading.width() >= section.width() - 4
        assert not section.expanded
        QTest.mouseClick(heading, Qt.MouseButton.LeftButton, pos=heading.rect().center())
        assert section.expanded
        assert section.content.isVisible()
        heading.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(heading, Qt.Key.Key_Space)
        assert not section.expanded
        assert section._summary.isVisible()
        section.close()
    finally:
        app.setStyle(original)


def test_header_has_platform_independent_custom_painter(app):
    section = AccordionSection("Séparateurs", QWidget())
    section.resize(560, 70)
    section.show()
    app.processEvents()
    # Captures of the heading should exist under any Qt style, not just Fusion.
    image = section._heading.grab().toImage()
    assert not image.isNull()
    assert image.width() > 400
    section.set_expanded(True)
    app.processEvents()
    expanded_image = section._heading.grab().toImage()
    assert not expanded_image.isNull()
    assert image.pixelColor(100, 10) != expanded_image.pixelColor(100, 10)
    section.close()
