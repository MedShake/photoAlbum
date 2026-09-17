from datetime import datetime
from pathlib import Path

import pytest
from PIL import ExifTags, Image

from photoalbum.metadata import ExifReader, PhotoAnalyzer
from photoalbum.models import DateSource


@pytest.mark.parametrize(
    "root_dates, nested_dates, expected",
    [
        ({}, {36867: "2024:06:15 12:34:56"}, datetime(2024, 6, 15, 12, 34, 56)),
        (
            {306: "2025:01:01 00:00:00"},
            {36867: "2024:06:15 12:34:56", 36868: "2024:07:01 00:00:00"},
            datetime(2024, 6, 15, 12, 34, 56),
        ),
        (
            {306: "2025:01:01 00:00:00"},
            {36867: "invalid", 36868: "2024:07:01 00:00:00"},
            datetime(2024, 7, 1),
        ),
        ({36867: "2024:06:15 12:34:56"}, {}, datetime(2024, 6, 15, 12, 34, 56)),
        (
            {36867: "2024:06:15 12:34:56"},
            {36868: "2024:07:01 00:00:00"},
            datetime(2024, 6, 15, 12, 34, 56),
        ),
        (
            {306: "2025:01:01 00:00:00"},
            {36867: "invalid"},
            datetime(2025, 1, 1),
        ),
        ({}, {36867: "invalid"}, None),
    ],
    ids=[
        "nested-original", "original-before-modification-and-digitized",
        "invalid-original-falls-back-to-digitized", "root-original",
        "root-original-before-nested-digitized", "fallback-to-root-datetime",
        "no-valid-exif-date",
    ],
)
def test_reads_jpeg_date_directories(tmp_path, root_dates, nested_dates, expected):
    # Numeric EXIF tags: DateTime (306), DateTimeOriginal (36867),
    # DateTimeDigitized (36868). Serialize and reopen a real JPEG so that
    # Pillow exposes the nested IFD through get_ifd(), not a flattened mock.
    path = tmp_path / "2020-02-03.jpg"
    exif = Image.Exif()
    for tag, value in root_dates.items():
        exif[tag] = value
    if nested_dates:
        exif[ExifTags.IFD.Exif] = nested_dates
    Image.new("RGB", (10, 10)).save(path, exif=exif)

    assert ExifReader().read(path).capture_datetime == expected

    photo = PhotoAnalyzer().analyze(path)
    assert photo.capture_datetime == (expected or datetime(2020, 2, 3))
    assert photo.date_source == (DateSource.EXIF if expected else DateSource.FILENAME)


def test_reads_image_dimensions(tmp_path: Path):
    image_path = tmp_path / "example.jpg"

    image = Image.new("RGB", (800, 600))
    image.save(image_path)

    reader = ExifReader()
    metadata = reader.read(image_path)

    assert metadata.width == 800
    assert metadata.height == 600


def test_image_without_exif_has_no_metadata(tmp_path: Path):
    image_path = tmp_path / "example.jpg"

    image = Image.new("RGB", (100, 100))
    image.save(image_path)

    reader = ExifReader()
    metadata = reader.read(image_path)

    assert metadata.orientation is None
    assert metadata.capture_datetime is None
    assert metadata.latitude is None
    assert metadata.longitude is None


def test_parse_valid_exif_datetime():
    result = ExifReader._parse_exif_datetime(
        "2025:06:15 14:30:45"
    )

    assert result == datetime(2025, 6, 15, 14, 30, 45)


def test_parse_invalid_exif_datetime():
    result = ExifReader._parse_exif_datetime(
        "not-a-date"
    )

    assert result is None


def test_convert_north_gps_coordinate():
    result = ExifReader._convert_gps_coordinate(
        (46, 30, 0),
        "N",
    )

    assert result == 46.5


def test_convert_south_gps_coordinate():
    result = ExifReader._convert_gps_coordinate(
        (46, 30, 0),
        "S",
    )

    assert result == -46.5


def test_convert_east_gps_coordinate():
    result = ExifReader._convert_gps_coordinate(
        (1, 15, 0),
        "E",
    )

    assert result == 1.25


def test_convert_west_gps_coordinate():
    result = ExifReader._convert_gps_coordinate(
        (1, 15, 0),
        "W",
    )

    assert result == -1.25
