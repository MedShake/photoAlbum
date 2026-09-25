from photoalbum.album import PageInstance
from dataclasses import replace
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize
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


def make_settings() -> AlbumStructureSettings:
    return AlbumStructureSettings(
        covers={
            position: CoverSettings(
                position=position,
                template_id="year-photo-scatter",
            )
            for position in CoverPosition
        },
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
            page_count=1,
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
    assert cache._pool.start.call_args_list[0].args[0].path == "/photo-0.jpg"
    assert "/photo-5.jpg" not in cache._queue
    for width in (310, 400, 550, 320):
        for page in pages:
            page.set_page_width(width)
        widget._request_page_images()
    assert cache._pool.start.call_count <= 2
    assert {worker.edge for worker in cache._active.values()} == {cache._edge}
    widget.clear()
    widget.close()
