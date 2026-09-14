from datetime import datetime
from pathlib import Path

from PIL import Image

from photoalbum.metadata import ExifReader


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

