from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt

from photoalbum.gui.models import PhotoTableModel
from photoalbum.models import (
    DateSource,
    LocationSource,
    Photo,
)


def test_empty_model_has_no_rows():
    model = PhotoTableModel()

    assert model.rowCount() == 0
    assert model.columnCount() == 8


def test_model_displays_photo_information():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        capture_datetime=datetime(
            2025,
            2,
            18,
            14,
            40,
            49,
        ),
        date_source=DateSource.EXIF,
        latitude=47.0,
        longitude=-1.0,
        city="Example City",
        location_source=LocationSource.GEOCODING,
    )

    model = PhotoTableModel([photo])

    assert model.data(
        model.index(0, 0),
        Qt.ItemDataRole.DisplayRole,
    ) == "👁  example.jpg"

    assert model.data(
        model.index(0, 1),
        Qt.ItemDataRole.DisplayRole,
    ) == ""

    assert model.data(
        model.index(0, 2),
        Qt.ItemDataRole.DisplayRole,
    ) == "2025-02-18 14:40:49"

    assert model.data(
        model.index(0, 4),
        Qt.ItemDataRole.DisplayRole,
    ) == "Yes"

    assert model.data(
        model.index(0, 5),
        Qt.ItemDataRole.DisplayRole,
    ) == "Example City"


def test_model_displays_date_anomaly():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
    )

    model = PhotoTableModel([photo])

    assert model.data(
        model.index(0, 7),
        Qt.ItemDataRole.DisplayRole,
    ) == "Missing date"


def test_user_role_returns_photo():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
    )

    model = PhotoTableModel([photo])

    assert (
        model.data(
            model.index(0, 0),
            Qt.ItemDataRole.UserRole,
        )
        is photo
    )


def test_set_photos_replaces_content():
    model = PhotoTableModel()

    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
    )

    model.set_photos([photo])

    assert model.rowCount() == 1
    assert model.photo_at(0) is photo
