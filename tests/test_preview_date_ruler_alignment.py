"""Date navigation starts at the top when its contents fit the viewport."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from photoalbum.gui.widgets.preview_navigation_ruler import (
    NavigationPage,
    PreviewNavigationRuler,
)
from photoalbum.i18n import Translator


@pytest.fixture(scope="module", autouse=True)
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def _ruler(mode: str, pages: list[NavigationPage], height: int = 600):
    ruler = PreviewNavigationRuler(Translator("fr"), mode=mode)
    ruler.resize(ruler.WIDTH, height)
    ruler.set_pages(pages)
    return ruler


def test_single_day_date_ruler_starts_at_top():
    ruler = _ruler("date", [NavigationPage(
        "05 janvier 2026", year=2026, month=1, day=5,
        dates=((2026, 1, 5),), page_number=1,
    )])
    try:
        rows = ruler._visible_rows()
        assert [ruler._date_entries[index].kind for index, _, _ in rows] == [
            "year", "month", "day",
        ]
        assert rows[0][1] - rows[0][2] / 2 == pytest.approx(0)
        assert rows[-1][1] + rows[-1][2] / 2 == pytest.approx(
            ruler.YEAR_HEIGHT + ruler.MONTH_HEIGHT + ruler.DAY_HEIGHT
        )
    finally:
        ruler.close()


def test_short_multiple_date_ruler_also_starts_at_top():
    ruler = _ruler("date", [
        NavigationPage("01 janvier 2026", 2026, 1, 1, page_number=1),
        NavigationPage("01 février 2026", 2026, 2, 1, page_number=2),
    ])
    try:
        rows = ruler._visible_rows()
        assert len(rows) == ruler._count()
        assert rows[0][1] - rows[0][2] / 2 == pytest.approx(0)
    finally:
        ruler.close()


def test_short_page_ruler_retains_centred_placement():
    ruler = _ruler("page", [
        NavigationPage("", page_number=1),
        NavigationPage("", page_number=2),
    ])
    try:
        rows = ruler._visible_rows()
        expected_top = (ruler.height() - 2 * ruler.PAGE_HEIGHT) / 2
        assert rows[0][1] - rows[0][2] / 2 == pytest.approx(expected_top)
    finally:
        ruler.close()


def test_long_date_ruler_still_scrolls_to_selected_period():
    pages = [NavigationPage(
        "", year=year, month=month, day=1,
        page_number=index + 1,
    ) for index, (year, month) in enumerate(
        (year, month) for year in (2025, 2026) for month in range(1, 13)
    )]
    ruler = _ruler("date", pages, height=300)
    try:
        assert ruler._row_tops[-1] > ruler.height()
        ruler.set_current_index(15)
        rows = ruler._visible_rows()
        assert rows[0][0] > 0
        assert len(rows) < ruler._count()
        assert 0 <= ruler._row_center_for(ruler._cursor()) <= ruler.height()
    finally:
        ruler.close()
