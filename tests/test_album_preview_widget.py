from photoalbum.album import PageInstance
from dataclasses import replace
from pathlib import Path
from time import monotonic

import pytest
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from photoalbum.album import (
    AlbumBuildResult,
    AlbumPlan,
    AlbumStructureSettings,
    US_LETTER,
    CoverPosition,
    CoverSettings,
    DividerSettings,
    PageNumberSettings,
    PageSide,
    PaginationResult,
    PhotoPageSettings,
    PlanItemKind,
    PlannedPage,
    PrintDiagnostic,
)
from photoalbum.template_engine import create_template_registry

from photoalbum.gui.widgets import AlbumPreviewWidget
from photoalbum.gui.widgets.album_preview_widget import (
    AlbumCoverPreview,
    AlbumPagePreview,
    PreviewThumbnailCache,
)
from photoalbum.models import Photo


@pytest.fixture(scope="module", autouse=True)
def application():
    # Ruler and cache tests must also work when run without a preview test first.
    app = QApplication.instance() or QApplication([])
    yield app


def _wait_for_preview_layout(widget: AlbumPreviewWidget) -> None:
    # set_result() queues resizing, which in turn queues layout/scroll updates.
    # One processEvents() call need not deliver this entire chain.
    deadline = monotonic() + 2
    while True:
        QTest.qWait(1)
        content_height = widget._content.height()
        viewport_height = widget._scroll.viewport().height()
        scroll = widget._scroll.verticalScrollBar()
        if (
            content_height == widget._pages_grid.sizeHint().height()
            and scroll.maximum() == content_height - viewport_height
            and scroll.maximum() > 0
            and all(
                page.geometry().bottom() < content_height
                for page in widget._page_widgets
            )
        ):
            widget._refresh_navigation_positions()
            return
        assert monotonic() < deadline, "Preview layout did not become scrollable"


def create_widget() -> AlbumPreviewWidget:
    if QApplication.instance() is None:
        QApplication([])

    return AlbumPreviewWidget(
        create_template_registry()
    )


def test_preview_default_geometry_respects_landscape():
    from photoalbum.album import PageOrientation

    widget = create_widget()
    widget.set_result(make_result(), replace(make_settings(), orientation=PageOrientation.LANDSCAPE))
    pages = widget.findChildren(AlbumCoverPreview) + widget.findChildren(AlbumPagePreview)
    assert pages
    for page in pages:
        assert (page._page_format.width_mm, page._page_format.height_mm) == (297.0, 210.0)
    widget.close()



def test_landscape_spreads_grow_on_wide_screens_without_enlarging_portrait():
    from photoalbum.album import PageOrientation

    landscape = create_widget()
    portrait = create_widget()
    try:
        landscape.set_result(
            make_result(),
            replace(make_settings(), orientation=PageOrientation.LANDSCAPE),
        )
        portrait.set_result(make_result(), make_settings())

        landscape._resize_page_widgets(viewport_width=1650)
        portrait._resize_page_widgets(viewport_width=1650)

        assert {page.width() for page in landscape._page_widgets} == {750}
        assert {page.width() for page in portrait._page_widgets} == {550}
        assert all(
            abs(page.height() - page.width() * 210 / 297) <= 1
            for page in landscape._page_widgets
        )
    finally:
        landscape.close()
        portrait.close()


def test_landscape_spreads_shrink_to_fit_with_navigation_ruler():
    from photoalbum.album import PageOrientation
    widget = create_widget()
    try:
        widget.set_result(
            make_result(),
            replace(make_settings(), orientation=PageOrientation.LANDSCAPE),
        )
        widget._resize_page_widgets(viewport_width=950)
        page_width = widget._page_widgets[0].width()
        margins = widget._pages_grid.contentsMargins()
        total_width = (
            page_width * 2
            + widget.SPREAD_HORIZONTAL_GAP
            + margins.left()
            + margins.right()
            + 8
        )

        assert 1 < page_width < 750
        assert total_width <= 950
        assert widget._date_ruler.width() == 54
        assert widget._page_ruler.width() == 54
        assert {page.width() for page in widget._page_widgets} == {page_width}

        widget._resize_page_widgets(viewport_width=1650)
        assert widget._page_widgets[0].width() > page_width
    finally:
        widget.close()


@pytest.mark.parametrize("density", [1.0, 2.0])
@pytest.mark.parametrize("page_format, orientation, expected_edge", [
    ("a4", "portrait", 778),
    ("a4", "landscape", 750),
    ("us-letter", "portrait", 712),
])
def test_image_requests_use_maximum_preview_size_across_resizes(
    monkeypatch, page_format, orientation, expected_edge, density,
):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from PySide6.QtGui import QImage
    from photoalbum.album import PageOrientation

    widget = create_widget()
    try:
        widget.set_result(
            make_result(),
            replace(make_settings(), page_format=page_format,
                    orientation=PageOrientation(orientation)),
        )
        cache = widget._thumbnail_cache
        cache._pool = SimpleNamespace(start=Mock())
        monkeypatch.setattr(widget, "devicePixelRatioF", lambda: density)
        widget._resize_page_widgets(viewport_width=950)
        widget._request_page_images()
        assert cache._edge == expected_edge * density
        assert cache._pool.start.call_count == 1
        worker = cache._pool.start.call_args.args[0]
        assert worker.edge == expected_edge * density
        image = QImage(40, 30, QImage.Format.Format_RGB32)
        image.fill(0xff123456)
        cache._finished(worker.token, image)
        original = cache.load(worker.path, QSize(40, 30))
        assert not original.isNull()

        for viewport_width in (1650, 600, 1200):
            widget._resize_page_widgets(viewport_width=viewport_width)
            widget._request_page_images()
            assert cache._edge == expected_edge * density
            assert cache._pool.start.call_count == 1
            assert cache.load(worker.path, QSize(100, 100)) is original

        # Plan hover previews share the same maximum resolution and cache.
        page = next(p for p in widget._page_widgets if isinstance(p, AlbumPagePreview))
        monkeypatch.setattr(page, "devicePixelRatioF", lambda: density)
        widget.prioritize_preview_images(page)
        assert cache._edge == expected_edge * density
        assert cache._pool.start.call_count == 1
    finally:
        widget.close()

def make_settings() -> AlbumStructureSettings:
    return AlbumStructureSettings(
        covers={
            position: CoverSettings(
                position=position,
                template_id="year-photo-scatter",
            )
            for position in CoverPosition
        },
        day_dividers=DividerSettings(enabled=False, template_id="day-divider-simple"),
        month_dividers=DividerSettings(
            enabled=True,
            template_id="month-divider-classic",
        ),
        year_dividers=DividerSettings(
            enabled=True,
            template_id="year-divider-classic",
        ),
        photo_pages=PhotoPageSettings(page=PageInstance(template_id='photo-page-1', settings={'photo_caption': {'show_datetime': True, 'show_location': True}})),
        page_numbers=PageNumberSettings(
            enabled=True,
        ),
    )


def make_result() -> AlbumBuildResult:
    photo = Photo(
        path=Path("/does/not/exist.jpg"),
        filename="photo.jpg",
    )

    return AlbumBuildResult(
        album_photos=(photo,),
        plan=AlbumPlan(),
        pagination=PaginationResult(
            pages=[
                PlannedPage(
                    number=1,
                    side=PageSide.RIGHT,
                    kind=PlanItemKind.PHOTO_GROUP,
                    template_id="photo-page-1",
                    photos=(photo,),
                    photo_capacity=1,
                )
            ]
        ),
        print_diagnostic=PrintDiagnostic(
            compatible=True,
            pages_to_add=0,
        ),
    )


def test_preview_starts_empty():
    widget = create_widget()

    assert widget._pages_grid.count() == 0


def test_preview_contains_covers_and_interior_pages():
    widget = create_widget()

    widget.set_result(
        make_result(),
        make_settings(),
    )

    # Four covers + one interior page.
    assert widget._pages_grid.count() == 5


def test_preview_clear_removes_everything():
    widget = create_widget()

    widget.set_result(
        make_result(),
        make_settings(),
    )

    widget.clear()

    assert widget._pages_grid.count() == 0


def test_front_cover_is_alone_on_the_right():
    widget = create_widget()

    widget.set_result(
        make_result(),
        make_settings(),
    )

    assert widget._pages_grid.itemAtPosition(
        0,
        0,
    ) is None

    item = widget._pages_grid.itemAtPosition(
        0,
        1,
    )

    assert item is not None
    assert isinstance(
        item.widget(),
        AlbumCoverPreview,
    )


def test_inside_front_faces_first_page():
    widget = create_widget()

    widget.set_result(
        make_result(),
        make_settings(),
    )

    left = widget._pages_grid.itemAtPosition(
        1,
        0,
    )
    right = widget._pages_grid.itemAtPosition(
        1,
        1,
    )

    assert left is not None
    assert right is not None

    assert isinstance(
        left.widget(),
        AlbumCoverPreview,
    )
    assert isinstance(
        right.widget(),
        AlbumPagePreview,
    )


def test_left_and_right_pages_share_a_spread():
    result = make_result()

    first = result.pagination.pages[0]

    result.pagination.pages = [
        first,
        PlannedPage(
            number=2,
            side=PageSide.LEFT,
            kind=PlanItemKind.PHOTO_GROUP,
            template_id="photo-page-1",
            photos=first.photos,
            photo_capacity=1,
        ),
        PlannedPage(
            number=3,
            side=PageSide.RIGHT,
            kind=PlanItemKind.PHOTO_GROUP,
            template_id="photo-page-1",
            photos=first.photos,
            photo_capacity=1,
        ),
    ]

    widget = create_widget()

    widget.set_result(
        result,
        make_settings(),
    )

    left = widget._pages_grid.itemAtPosition(
        2,
        0,
    )
    right = widget._pages_grid.itemAtPosition(
        2,
        1,
    )

    assert left is not None
    assert right is not None

    assert isinstance(
        left.widget(),
        AlbumPagePreview,
    )
    assert isinstance(
        right.widget(),
        AlbumPagePreview,
    )


def test_inside_back_is_on_the_right():
    widget = create_widget()

    widget.set_result(
        make_result(),
        make_settings(),
    )

    item = widget._pages_grid.itemAtPosition(
        2,
        1,
    )

    assert item is not None
    assert isinstance(
        item.widget(),
        AlbumCoverPreview,
    )


def test_back_cover_is_alone_on_the_left():
    widget = create_widget()

    widget.set_result(
        make_result(),
        make_settings(),
    )

    item = widget._pages_grid.itemAtPosition(
        3,
        0,
    )

    assert item is not None
    assert isinstance(
        item.widget(),
        AlbumCoverPreview,
    )

    assert widget._pages_grid.itemAtPosition(
        3,
        1,
    ) is None


def test_thumbnail_cache_applies_exif_orientation(
    tmp_path,
):
    path = tmp_path / "rotated.jpg"

    image = Image.new(
        "RGB",
        (80, 40),
    )

    exif = Image.Exif()
    exif[274] = 6

    image.save(
        path,
        exif=exif,
    )

    cache = PreviewThumbnailCache()

    pixmap = cache.load(
        path,
        QSize(200, 200),
    )

    assert not pixmap.isNull()

    # Original file is landscape.
    # EXIF orientation 6 displays it in portrait.
    assert pixmap.height() > pixmap.width()



def test_preview_uses_page_format_from_settings():
    widget = create_widget()

    settings = replace(
        make_settings(),
        page_format="us-letter",
    )

    widget.set_result(
        make_result(),
        settings,
    )

    item = widget._pages_grid.itemAtPosition(
        1,
        1,
    )

    assert item is not None

    preview = item.widget()

    assert isinstance(
        preview,
        AlbumPagePreview,
    )

    assert preview._page_format == US_LETTER


def _finish_images(cache, paths):
    import time
    cache.prioritize(paths)
    deadline = time.monotonic() + 3
    while cache._active or cache._queue:
        QApplication.processEvents()
        assert time.monotonic() < deadline
        time.sleep(0.001)


def test_rebuilding_pages_preserves_preview_image(tmp_path):
    widget = create_widget()
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (80, 40), "red").save(path)
    cache = widget._thumbnail_cache
    _finish_images(cache, [path])
    first = cache.load(path, QSize(30, 20))
    assert not first.isNull()
    widget.set_result(make_result(), make_settings())
    old_pages = tuple(widget._page_widgets)
    result = make_result()
    result.pagination.pages[0].photos[0].caption = "New caption"
    widget.set_result(result, make_settings())
    assert tuple(widget._page_widgets) != old_pages
    assert cache.load(path, QSize(60, 40)) is first
    widget.clear()
    assert cache.load(path, QSize(30, 20)).isNull()
    widget.close()


def test_rebuilding_pages_invalidates_only_changed_sources(tmp_path):
    widget = create_widget()
    path, stable, missing = [tmp_path / name for name in ("changed.jpg", "stable.jpg", "missing.jpg")]
    for source in (path, stable):
        Image.new("RGB", (80, 40), "red").save(source)
    cache = widget._thumbnail_cache
    _finish_images(cache, [path, stable, missing])
    unchanged = cache.load(stable, QSize(30, 20))
    assert cache.load(missing, QSize(30, 20)).isNull()
    Image.new("RGB", (160, 100), "blue").save(path)
    Image.new("RGB", (80, 40), "green").save(missing)
    widget.set_result(make_result(), make_settings())
    widget._image_request_timer.stop()
    _finish_images(cache, [path, stable, missing])
    assert cache.load(path, QSize(30, 20)).toImage().pixelColor(0, 0).blue() > 200
    assert cache.load(stable, QSize(30, 20)) is unchanged
    assert not cache.load(missing, QSize(30, 20)).isNull()
    path.unlink()
    widget.set_result(make_result(), make_settings())
    assert cache.load(path, QSize(30, 20)).isNull()
    widget.clear()
    widget.close()


def test_preview_prioritizes_visible_pages_and_reuses_resize_requests(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    widget = create_widget()
    result = make_result()
    base = result.pagination.pages[0]
    result.pagination.pages[:] = [
        replace(base, number=index + 1, photos=(Photo(
            path=Path(f"/photo-{index}.jpg"), filename=f"photo-{index}.jpg",
        ),)) for index in range(6)
    ]
    widget.set_result(result, make_settings())
    cache = widget._thumbnail_cache
    cache._pool = SimpleNamespace(start=Mock())
    pages = [p for p in widget._page_widgets if isinstance(p, AlbumPagePreview)]
    height = widget._scroll.viewport().height()
    for index, page in enumerate(pages):
        page.move(0, index * (height + page.height() + 10))
    monkeypatch.setattr(widget, "isVisible", lambda: True)
    widget._request_page_images()
    initial_edge = cache._edge
    assert cache._pool.start.call_args_list[0].args[0].path == "/photo-0.jpg"
    assert "/photo-5.jpg" not in cache._queue
    for width in (310, 400, 550, 320):
        for page in pages:
            page.set_page_width(width)
        widget._request_page_images()
    assert cache._pool.start.call_count <= 2
    # Both running and future decodes keep the maximum useful resolution.
    from math import ceil
    assert cache._edge == initial_edge == ceil(778 * widget.devicePixelRatioF())
    assert {worker.edge for worker in cache._active.values()} == {initial_edge}
    widget.clear()
    widget.close()


def test_public_preview_factories_reuse_preview_tab_cache():
    widget = create_widget()
    try:
        result = make_result()
        settings = make_settings()
        widget.set_result(result, settings)

        page_preview = widget.create_page_preview(
            result.pagination.pages[0], settings
        )
        cover_preview = widget.create_cover_preview(
            settings, CoverPosition.FRONT
        )

        assert page_preview._thumbnail_cache is widget._thumbnail_cache
        assert cover_preview._thumbnail_cache is widget._thumbnail_cache
        assert page_preview._render_service is widget._render_service
        assert cover_preview._render_service is widget._render_service
    finally:
        widget.close()


def test_two_lateral_rulers_include_covers_and_observed_dates():
    from datetime import datetime

    result = make_result()
    photo = replace(result.pagination.pages[0].photos[0],
                    capture_datetime=datetime(2025, 8, 14))
    page = replace(result.pagination.pages[0], photos=(photo,))
    result.pagination.pages[:] = [
        page,
        replace(page, number=2, side=PageSide.LEFT,
                year=2025, month=9, photos=()),
        replace(page, number=3, side=PageSide.RIGHT,
                year=2026, month=None, photos=()),
    ]
    from photoalbum.i18n import Translator
    widget = AlbumPreviewWidget(create_template_registry(), translator=Translator("fr"))
    try:
        widget.set_result(result, make_settings())
        dates, pages = widget._date_ruler, widget._page_ruler
        assert dates._mode == "date" and pages._mode == "page"
        assert len(pages._pages) == len(dates._pages) == 7
        assert len(widget._navigation_widgets) == 7
        assert [p.short_label for p in pages._pages] == [
            "1re c.", "2e c.", "1", "2", "3", "3e c.", "4e c.",
        ]
        assert [p.date_label for p in dates._pages[2:5]] == [
            "14 août 2025", "septembre 2025", "2026",
        ]
        assert [e.kind for e in dates._date_entries] == [
            "year", "month", "day", "month", "year",
        ]
        assert [e.short_label for e in dates._date_entries] == [
            "2025", "aoû 25", "14", "sep 25", "2026",
        ]
        assert dates.width() == pages.width() == 54
        assert widget.layout().itemAt(0).widget() is dates
        assert widget.layout().itemAt(2).widget() is pages
    finally:
        widget.close()


def test_both_rulers_navigate_and_follow_scroll():
    result = make_result()
    base = result.pagination.pages[0]
    result.pagination.pages[:] = [
        replace(base, number=number,
                side=PageSide.RIGHT if number % 2 else PageSide.LEFT)
        for number in range(1, 9)
    ]
    widget = create_widget()
    try:
        widget.resize(1000, 480)
        widget.show()
        QApplication.processEvents()
        widget.set_result(result, make_settings())
        _wait_for_preview_layout(widget)
        widget._navigate_to_page(8)
        assert widget._date_ruler._current_index == 8
        assert widget._page_ruler._current_index == 8
        assert widget._scroll.verticalScrollBar().value() > 0
        assert widget._navigation_widgets[7].y() == widget._navigation_widgets[8].y()
        widget._scroll.verticalScrollBar().setValue(0)
        assert widget._page_ruler._current_index == 0
        assert widget._date_ruler._current_index == 0
        widget._page_ruler._choose(11)  # Back cover.
        assert widget._scroll.verticalScrollBar().value() > 0
        assert widget._page_ruler._current_index == 11
        assert widget._date_ruler._current_index == 11
    finally:
        widget.close()


def test_date_ruler_uses_compact_ticks_and_years_on_month_labels():
    from photoalbum.gui.widgets.preview_navigation_ruler import (
        NavigationPage, PreviewNavigationRuler,
    )
    from photoalbum.i18n import Translator

    ruler = PreviewNavigationRuler(Translator("fr"), mode="date")
    try:
        pages = [
            NavigationPage("01/01/2021", 2021, 1, 1),
            NavigationPage("02/01/2021 – 09/01/2021", 2021, 1, 2,
                           dates=((2021, 1, 2), (2021, 1, 9))),
            NavigationPage("03/02/2022", 2022, 2, 3),
        ]
        ruler.set_pages(pages)
        entries = ruler._date_entries
        assert [(e.kind, e.period) for e in entries] == [
            ("year", (2021,)), ("month", (2021, 1)),
            ("day", (2021, 1, 1)), ("day", (2021, 1, 2)),
            ("day", (2021, 1, 9)), ("year", (2022,)),
            ("month", (2022, 2)), ("day", (2022, 2, 3)),
        ]
        assert [e.page_index for e in entries] == [0, 0, 0, 1, 1, 2, 2, 2]
        assert entries[1].short_label == "jan 21"
        assert entries[6].short_label == "fév 22"
        assert ruler._item_height(0) > ruler._item_height(1) > ruler._item_height(2)
        assert ruler._item_height(2) == ruler.DAY_HEIGHT
        assert ruler.WIDTH == 54
        assert ruler.YEAR_FONT_SIZE >= 13
        assert ruler.MONTH_FONT_SIZE >= 12
        assert ruler.PAGE_FONT_SIZE >= 12
    finally:
        ruler.close()


def test_bounded_rulers_stop_at_ends_and_date_periods_jump_to_first_page():
    from photoalbum.gui.widgets.preview_navigation_ruler import (
        NavigationPage, PreviewNavigationRuler,
    )
    from photoalbum.i18n import Translator

    pages = [
        NavigationPage("", short_label="1re c."),
        NavigationPage("03/01/2024", 2024, 1, 3, page_number=1),
        NavigationPage("04/02/2024", 2024, 2, 4, page_number=2),
        NavigationPage("02/01/2025", 2025, 1, 2, page_number=3),
        NavigationPage("", short_label="4e c."),
    ]
    date = PreviewNavigationRuler(Translator("fr"), mode="date")
    page = PreviewNavigationRuler(Translator("fr"), mode="page")
    try:
        for ruler in (date, page):
            ruler.resize(54, 480)
            ruler.set_pages(pages)
        activated: list[int] = []
        date.page_activated.connect(activated.append)
        page.page_activated.connect(activated.append)
        page._choose(-1)
        assert (page._current_index, activated[-1]) == (0, 0)
        page._choose(5)
        assert (page._current_index, activated[-1]) == (4, 4)
        assert [index for index, _, _ in page._visible_rows()] == list(range(5))
        assert len({index for index, _, _ in date._visible_rows()}) == len(date._date_entries)
        years = [i for i, e in enumerate(date._date_entries) if e.kind == "year"]
        assert len(years) == 2
        date._choose(years[1])
        assert activated[-1] == 3
        assert date._date_cursor == years[1]
        month = next(i for i, e in enumerate(date._date_entries)
                     if e.period == (2024, 2))
        date._choose(month)
        assert activated[-1] == 2
        assert date._date_cursor == month
        assert not hasattr(page, "SEAM_HEIGHT")
        assert not hasattr(date, "_seam_after")
    finally:
        date.close()
        page.close()


def test_large_page_ruler_has_fixed_ends_and_paints_only_visible_rows():
    from photoalbum.gui.widgets.preview_navigation_ruler import (
        NavigationPage, PreviewNavigationRuler,
    )
    from photoalbum.i18n import Translator

    ruler = PreviewNavigationRuler(Translator("fr"), mode="page")
    try:
        ruler.resize(54, 420)
        ruler.set_pages([
            NavigationPage("14/08/2025", 2025, 8, 14, page_number=number)
            for number in range(1, 1325)
        ])
        assert len(ruler._row_tops) == 1325
        assert ruler._visible_rows()[0][0] == 0
        assert len(ruler._visible_rows()) <= 19

        ruler.set_current_index(650)
        middle = ruler._visible_rows()
        assert middle[0][0] < 650 < middle[-1][0]
        assert len(middle) <= 19
        assert len({index for index, _, _ in middle}) == len(middle)

        ruler.set_current_index(1323)
        assert ruler._visible_rows()[-1][0] == 1323
        ruler._choose(1324)
        assert ruler._current_index == 1323  # No wrap to page 1.
        ruler._choose(-20)
        assert ruler._current_index == 0  # No wrap to the last page.
        assert ruler._visible_rows()[0][0] == 0
    finally:
        ruler.close()


def test_date_ruler_preserves_divider_configuration():
    from photoalbum.gui.widgets.preview_navigation_ruler import (
        NavigationPage, PreviewNavigationRuler,
    )
    from photoalbum.i18n import Translator

    ruler = PreviewNavigationRuler(Translator("en"), mode="date")
    try:
        pages = [NavigationPage("2024", 2024, divider_level="year"),
                 NavigationPage("14/01/2024", 2024, 1, 14)]
        ruler.set_pages(pages, enabled_dividers=("year",))
        assert ruler._enabled_dividers == {"year"}
        ruler.set_pages(pages, enabled_dividers=())
        assert not ruler._enabled_dividers
    finally:
        ruler.close()


def test_callouts_point_inwards_and_show_both_page_and_date():
    from PySide6.QtWidgets import QWidget
    from photoalbum.gui.widgets.preview_navigation_ruler import (
        NavigationPage, PreviewNavigationRuler,
    )
    from photoalbum.i18n import Translator

    parent = QWidget()
    date = PreviewNavigationRuler(Translator("fr"), parent, mode="date")
    page = PreviewNavigationRuler(Translator("fr"), parent, mode="page")
    try:
        parent.resize(650, 450)
        date.move(0, 0)
        page.move(596, 0)
        date.resize(54, 450)
        page.resize(54, 450)
        parent.show()
        QApplication.processEvents()
        pages = [NavigationPage("14/08/2024", 2024, 8, 14, page_number=1),
                 NavigationPage("15/08/2024", 2024, 8, 15, page_number=2)]
        date.set_pages(pages)
        page.set_pages(pages)
        page._hover_at(page._row_center_for(0))
        assert page._callout is not None and page._callout.isVisible()
        assert page._callout._first_line == "Page 1 / 2"
        assert page._callout._second_line == "14/08/2024"
        assert page._callout.geometry().right() <= page.geometry().left() + 1
        date._hover_at(date._row_center_for(1))
        assert date._callout is not None and date._callout.isVisible()
        assert date._callout._first_line == "Page 1 / 2"
        assert date._callout._second_line == "août 2024"
        assert date._callout.geometry().left() >= date.geometry().right() - 1
        date._hide_callout()
        page._hide_callout()
        assert not date._callout.isVisible() and not page._callout.isVisible()
    finally:
        parent.close()


def test_ruler_wheel_explores_both_indexes_without_scrolling_preview():
    """Wheel browsing is a two-ruler transaction, not a preview navigation."""
    from datetime import datetime
    from types import SimpleNamespace
    from PySide6.QtCore import QPoint, QPointF

    result = make_result()
    base = result.pagination.pages[0]
    result.pagination.pages[:] = [
        replace(base, number=number,
                side=PageSide.RIGHT if number % 2 else PageSide.LEFT,
                photos=(replace(base.photos[0], capture_datetime=datetime(
                    2024 if number <= 6 else 2025, 1 if number <= 6 else 5,
                    number)),))
        for number in range(1, 13)
    ]
    widget = create_widget()
    try:
        widget.resize(1000, 470)
        widget.show()
        QApplication.processEvents()
        widget.set_result(result, make_settings())
        _wait_for_preview_layout(widget)
        widget._navigate_to_page(7)
        scroll = widget._scroll.verticalScrollBar()
        original_scroll = scroll.value()
        assert original_scroll > 0
        date, page = widget._date_ruler, widget._page_ruler
        assert date._current_index == page._current_index == 7

        accepted = []
        event = SimpleNamespace(
            angleDelta=lambda: QPoint(0, -120),
            pixelDelta=lambda: QPoint(0, 0),
            position=lambda: QPointF(20, 200),
            accept=lambda: accepted.append(True),
        )
        page.wheelEvent(event)
        assert accepted
        assert scroll.value() == original_scroll
        assert date._current_index == page._current_index == 7  # Displayed.
        assert page._cursor() == 8  # Explored.
        assert date._cursor() == date._date_cursor_for_page(8)
        assert date._explore_index == page._explore_index == 8

        # Exploring an exact month/year row preserves that row (even though
        # its destination is the period's first physical page).
        date_entry = next(i for i, entry in enumerate(date._date_entries)
                          if entry.kind == "month")
        date._explore(date_entry)
        destination = date._date_entries[date_entry].page_index
        assert date._cursor() == date_entry
        assert page._cursor() == destination
        assert scroll.value() == original_scroll
        assert date._current_index == page._current_index == 7

        # A click, unlike browsing, commits the new preview position.
        page._choose(10)
        assert scroll.value() != original_scroll
        assert date._current_index == page._current_index == 10
        assert page._explore_index is None
        assert date._explore_index is None

        # Scrolling the real preview takes over again and resets browsing.
        page._explore(6)
        assert page._explore_index == 6
        scroll.setValue(0)
        assert date._explore_index is None and page._explore_index is None
        assert date._current_index == page._current_index == 0
    finally:
        widget.close()


def test_date_browsing_keeps_year_and_month_rows_until_next_action():
    app = QApplication.instance() or QApplication([])
    from photoalbum.gui.widgets.preview_navigation_ruler import (
        NavigationPage, PreviewNavigationRuler,
    )
    from photoalbum.i18n import Translator

    pages = [
        NavigationPage("14/08/2021", 2021, 8, 14, page_number=1),
        NavigationPage("23/09/2021", 2021, 9, 23, page_number=2),
        NavigationPage("02/01/2022", 2022, 1, 2, page_number=3),
    ]
    ruler = PreviewNavigationRuler(Translator("fr"), mode="date")
    try:
        ruler.resize(54, 320)
        ruler.set_pages(pages)
        explored = []
        activated = []
        ruler.page_explored.connect(lambda page, row: explored.append((page, row)))
        ruler.page_activated.connect(activated.append)
        year = next(i for i, item in enumerate(ruler._date_entries)
                    if item.period == (2022,))
        ruler._explore(year)
        assert explored[-1] == (2, year)
        assert not activated
        assert ruler._cursor() == year
        assert ruler._current_index == 0
        assert ruler._preview_cursor() != ruler._cursor()
        ruler._choose(year)
        assert activated == [2]
        assert ruler._cursor() == year
        assert ruler._explore_index is None
    finally:
        ruler.close()


def test_drag_browses_and_click_commits():
    app = QApplication.instance() or QApplication([])
    from types import SimpleNamespace
    from PySide6.QtCore import QPointF, Qt
    from photoalbum.gui.widgets.preview_navigation_ruler import (
        NavigationPage, PreviewNavigationRuler,
    )
    from photoalbum.i18n import Translator

    ruler = PreviewNavigationRuler(Translator("fr"), mode="page")
    try:
        ruler.resize(54, 320)
        ruler.set_pages([NavigationPage("14/08/2024", 2024, 8, 14,
                                       page_number=i + 1) for i in range(20)])
        explored, activated = [], []
        ruler.page_explored.connect(lambda page, row: explored.append(page))
        ruler.page_activated.connect(activated.append)

        def mouse(y):
            return SimpleNamespace(button=lambda: Qt.MouseButton.LeftButton,
                                   position=lambda: QPointF(12, y),
                                   accept=lambda: None)

        y = ruler._row_center_for(0)
        ruler.mousePressEvent(mouse(y))
        ruler.mouseMoveEvent(mouse(y - 40))
        assert explored and not activated
        assert ruler._current_index == 0
        assert ruler._explore_index is not None
        ruler.mouseReleaseEvent(mouse(y - 40))
        assert not activated  # Dragging doesn't jump to the preview.
        assert ruler._explore_index is not None

        cursor_y = ruler._row_center_for(ruler._cursor())
        selected = ruler._hit_at(cursor_y)[0]
        ruler.mousePressEvent(mouse(cursor_y))
        ruler.mouseReleaseEvent(mouse(cursor_y))
        assert activated == [selected]
        assert ruler._explore_index is None
    finally:
        ruler.close()


def test_navigation_day_ticks_are_compact_and_dates_use_month_names():
    from photoalbum.gui.widgets.preview_navigation_ruler import PreviewNavigationRuler
    from photoalbum.i18n import Translator
    from datetime import datetime

    ruler = PreviewNavigationRuler(Translator("fr"), mode="date")
    assert ruler.DAY_HEIGHT == 7
    ruler.close()
    page = make_result().pagination.pages[0]
    dated = replace(page, photos=(replace(page.photos[0],
                    capture_datetime=datetime(2026, 9, 8)),))
    navigation = AlbumPreviewWidget._navigation_page(dated, Translator("fr"))
    assert navigation.date_label == "08 septembre 2026"
