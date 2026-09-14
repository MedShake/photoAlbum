from datetime import datetime
from pathlib import Path

from photoalbum.models import DateSource, Photo


def test_photo_without_date_is_an_anomaly():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
    )

    assert photo.capture_datetime is None
    assert photo.date_source == DateSource.UNKNOWN
    assert photo.is_date_anomaly is True


def test_photo_with_exif_date_is_not_an_anomaly():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        capture_datetime=datetime(2025, 6, 15, 14, 30, 0),
        date_source=DateSource.EXIF,
    )

    assert photo.has_capture_datetime is True
    assert photo.is_date_anomaly is False


def test_photo_with_manual_date_is_not_an_anomaly():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        capture_datetime=datetime(2025, 6, 15, 14, 30, 0),
        date_source=DateSource.MANUAL,
    )

    assert photo.date_source == DateSource.MANUAL
    assert photo.is_date_anomaly is False


def test_photo_gps_detection():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        latitude=46.123,
        longitude=-1.234,
    )

    assert photo.has_gps is True


def test_photo_without_complete_gps_is_not_geolocated():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        latitude=46.123,
    )

    assert photo.has_gps is False

