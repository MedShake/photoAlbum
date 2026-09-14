from PySide6.QtCore import Qt

from photoalbum.album import (
    BlankPageReason,
    PageSide,
    PlanItemKind,
    PlannedPage,
)
from photoalbum.gui.models import AlbumPageTableModel


def test_empty_album_page_model():
    model = AlbumPageTableModel()

    assert model.rowCount() == 0
    assert model.columnCount() == 8


def test_model_displays_normal_page():
    page = PlannedPage(
        number=3,
        side=PageSide.RIGHT,
        kind=PlanItemKind.MONTH_DIVIDER,
        template_id="month",
        year=2025,
        month=3,
    )

    model = AlbumPageTableModel([page])

    assert model.data(
        model.index(0, 0),
        Qt.ItemDataRole.DisplayRole,
    ) == "3"

    assert model.data(
        model.index(0, 1),
        Qt.ItemDataRole.DisplayRole,
    ) == "right"

    assert model.data(
        model.index(0, 2),
        Qt.ItemDataRole.DisplayRole,
    ) == "month_divider"

    assert model.data(
        model.index(0, 4),
        Qt.ItemDataRole.DisplayRole,
    ) == "2025-03"


def test_model_displays_photo_capacity():
    page = PlannedPage(
        number=4,
        side=PageSide.LEFT,
        kind=PlanItemKind.PHOTO_GROUP,
        template_id="photo-2",
        photo_capacity=2,
    )

    model = AlbumPageTableModel([page])

    assert model.data(
        model.index(0, 6),
        Qt.ItemDataRole.DisplayRole,
    ) == "2"


def test_model_displays_technical_blank():
    page = PlannedPage(
        number=4,
        side=PageSide.LEFT,
        kind=None,
        template_id="photo-2",
        photo_capacity=2,
        blank_reason=BlankPageReason.TECHNICAL,
    )

    model = AlbumPageTableModel([page])

    assert model.data(
        model.index(0, 2),
        Qt.ItemDataRole.DisplayRole,
    ) == "blank"

    assert model.data(
        model.index(0, 7),
        Qt.ItemDataRole.DisplayRole,
    ) == "technical"


def test_user_role_returns_planned_page():
    page = PlannedPage(
        number=1,
        side=PageSide.RIGHT,
        kind=None,
        template_id=None,
    )

    model = AlbumPageTableModel([page])

    assert (
        model.data(
            model.index(0, 0),
            Qt.ItemDataRole.UserRole,
        )
        is page
    )

