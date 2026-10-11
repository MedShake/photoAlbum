"""Regression checks for the inward-pointing page/date navigation panels."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from photoalbum.gui.widgets.preview_navigation_ruler import (
    NavigationPage,
    PreviewNavigationRuler,
    _RulerCallout,
)
from photoalbum.i18n import Translator


@pytest.fixture(scope="module", autouse=True)
def application():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize("side", ["left", "right"])
def test_pointed_outline_is_one_closed_shape_without_join_line(side):
    parent = QWidget()
    popup = _RulerCallout(parent, side=side)
    try:
        popup.display("Page 5 / 200", "05 janvier 2027", QPoint(200, 90))
        shape = popup._outline_path()
        # The pointer and the body share one contour, not two overlaid borders.
        assert shape.isEmpty() is False
        # No segment must cut through the centre of the pointer/body junction.
        # The old two-shape implementation drew exactly such a vertical stroke.
        left, right = popup._body_edges()
        junction = left if side == "left" else right
        inward = junction + 2 if side == "left" else junction - 2
        outward = junction - 2 if side == "left" else junction + 2
        assert shape.contains(QPointF(inward, popup._arrow_y))
        assert shape.contains(QPointF(outward, popup._arrow_y))
    finally:
        parent.close()


@pytest.mark.parametrize("lang,connecting_word", [("fr", "au"), ("en", "to")])
def test_multi_date_page_range_uses_two_lines_and_expands(lang, connecting_word):
    parent = QWidget()
    parent.resize(600, 320)
    ruler = PreviewNavigationRuler(Translator(lang), parent, mode="page")
    ruler.resize(ruler.WIDTH, 320)
    ruler.move(0, 0)
    page_dates = (
        (2026, 12, 30),
        (2027, 1, 5),
    )
    page = NavigationPage(
        "30 décembre 2026 – 05 janvier 2027",
        2026, 12, 30, dates=page_dates, page_number=1,
    )
    try:
        parent.show()
        QApplication.processEvents()
        ruler.set_pages([page])
        ruler._hover_at(ruler._row_center_for(0))
        popup = ruler._callout
        assert popup is not None and popup.isVisible()
        assert popup._second_line == (
            f"30 décembre 2026\n{connecting_word} 05 janvier 2027"
        )
        assert popup.height() > popup.HEIGHT
        assert popup.height() >= popup.TEXT_TOP + popup._date_height() + 10
        assert popup.geometry().right() <= parent.width()
        assert popup.geometry().bottom() <= parent.height()
        ruler.set_pages([NavigationPage("30 décembre 2026", page_number=1)])
        ruler._hover_at(ruler._row_center_for(0))
        assert popup._second_line == "30 décembre 2026"
        assert popup.height() == popup.HEIGHT
    finally:
        parent.close()


def test_single_date_ruler_callout_remains_compact_and_keeps_single_date():
    parent = QWidget()
    parent.resize(650, 350)
    ruler = PreviewNavigationRuler(Translator("fr"), parent, mode="date")
    ruler.move(parent.width() - ruler.width(), 0)
    ruler.resize(ruler.WIDTH, parent.height())
    try:
        parent.show()
        QApplication.processEvents()
        ruler.set_pages([NavigationPage("30 décembre 2026 – 05 janvier 2027",
                                        2026, 12, 30,
                                        dates=((2026, 12, 30), (2027, 1, 5)),
                                        page_number=1)])
        first_day = next(i for i, entry in enumerate(ruler._date_entries)
                         if entry.kind == "day")
        ruler._update_callout(first_day, ruler._row_center_for(first_day))
        popup = ruler._callout
        assert popup is not None
        assert popup.height() == popup.HEIGHT
        assert "\n" not in popup._second_line
        assert popup.geometry().left() >= 0
    finally:
        parent.close()


def test_callout_keeps_blue_highlight_outline_on_both_sides():
    """The border must use the native highlight role, not the grey mid role."""
    parent = QWidget()
    parent.resize(500, 300)
    try:
        for side in ("left", "right"):
            popup = _RulerCallout(parent, side=side)
            palette = popup.palette()
            palette.setColor(QPalette.ColorRole.Base, QColor(250, 250, 250))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 85, 220))
            palette.setColor(QPalette.ColorRole.Mid, QColor(180, 80, 30))
            popup.setPalette(palette)
            popup.display("Page 5 / 200", "05 janvier 2027", QPoint(200, 90))
            image = QImage(popup.size(), QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            popup.render(image)
            # The central part of the top outline is unaffected by the tip.
            border_pixel = image.pixelColor(popup.width() // 2, 1)
            assert border_pixel.blue() > border_pixel.red(), side
            assert border_pixel.blue() > border_pixel.green(), side
            popup.close()
    finally:
        parent.close()
