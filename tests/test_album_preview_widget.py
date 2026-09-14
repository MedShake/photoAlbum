from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from photoalbum.album import (
    AlbumBuildResult,
    AlbumPlan,
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerSettings,
    PageNumberSettings,
    PageSide,
    PaginationResult,
    PhotoCaptionSettings,
    PhotoPageSettings,
    PlanItemKind,
    PlannedPage,
    PrintDiagnostic,
    create_builtin_template_registry,
)
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
        create_builtin_template_registry()
    )


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
        photo_pages=PhotoPageSettings(
            template_id="photo-page-1",
            caption=PhotoCaptionSettings(
                show_datetime=True,
                show_location=True,
            ),
        ),
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
