from datetime import datetime
from pathlib import Path

from PIL import Image

from photoalbum.metadata import PhotoAnalyzer
from photoalbum.models import DateSource, GpsSource


def test_analyzer_uses_exif_date_when_available(tmp_path: Path):
    image_path = tmp_path / "2025-01-01.jpg"

    image = Image.new("RGB", (640, 480))

    exif = Image.Exif()
    exif[36867] = "2024:12:25 10:30:45"

    image.save(image_path, exif=exif)

    analyzer = PhotoAnalyzer()
    photo = analyzer.analyze(image_path)

    assert photo.capture_datetime == datetime(
        2024,
        12,
        25,
        10,
        30,
        45,
    )
    assert photo.date_source == DateSource.EXIF
    assert photo.exif_capture_datetime == datetime(
        2024,
        12,
        25,
        10,
        30,
        45,
    )
    assert photo.original_capture_datetime == datetime(
        2024,
        12,
        25,
        10,
        30,
        45,
    )
    assert photo.original_date_source == DateSource.EXIF


def test_analyzer_uses_filename_when_exif_date_is_missing(
    tmp_path: Path,
):
    image_path = tmp_path / "IMG_20250615_143045.jpg"

    image = Image.new("RGB", (800, 600))
    image.save(image_path)

    analyzer = PhotoAnalyzer()
    photo = analyzer.analyze(image_path)

    assert photo.capture_datetime == datetime(
        2025,
        6,
        15,
        14,
        30,
        45,
    )
    assert photo.date_source == DateSource.FILENAME
    assert photo.exif_capture_datetime is None
    assert photo.original_capture_datetime == datetime(
        2025,
        6,
        15,
        14,
        30,
        45,
    )
    assert photo.original_date_source == DateSource.FILENAME


def test_analyzer_marks_photo_without_date_as_anomaly(
    tmp_path: Path,
):
    image_path = tmp_path / "holiday.jpg"

    image = Image.new("RGB", (1024, 768))
    image.save(image_path)

    analyzer = PhotoAnalyzer()
    photo = analyzer.analyze(image_path)

    assert photo.capture_datetime is None
    assert photo.date_source == DateSource.UNKNOWN
    assert photo.is_date_anomaly is True


def test_analyzer_reads_image_dimensions(tmp_path: Path):
    image_path = tmp_path / "example.jpg"

    image = Image.new("RGB", (1600, 1200))
    image.save(image_path)

    analyzer = PhotoAnalyzer()
    photo = analyzer.analyze(image_path)

    assert photo.width == 1600
    assert photo.height == 1200


def test_analyzer_reads_file_information(tmp_path: Path):
    image_path = tmp_path / "2025-06-15.jpg"

    image = Image.new("RGB", (320, 240))
    image.save(image_path)

    expected_stat = image_path.stat()

    analyzer = PhotoAnalyzer()
    photo = analyzer.analyze(image_path)

    assert photo.file_size == expected_stat.st_size
    assert photo.modified_time_ns == expected_stat.st_mtime_ns
    assert photo.content_hash is None


def test_analyzer_exposes_exif_gps_as_v3_candidate(tmp_path: Path):
    class FakeMetadata:
        width = 640
        height = 480
        orientation = 1
        capture_datetime = None
        latitude = 47.2184
        longitude = -1.5536

    class FakeExifReader:
        def read(self, path: Path):
            return FakeMetadata()

    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"placeholder")

    analyzer = PhotoAnalyzer(exif_reader=FakeExifReader())
    photo = analyzer.analyze(image_path)

    assert (photo.latitude, photo.longitude) == (
        47.2184,
        -1.5536,
    )
    assert photo.gps_source == GpsSource.EXIF

    assert (photo.exif_latitude, photo.exif_longitude) == (
        47.2184,
        -1.5536,
    )
    assert (photo.original_latitude, photo.original_longitude) == (
        47.2184,
        -1.5536,
    )

    assert photo.source_latitude is None
    assert photo.source_longitude is None


def test_analyzer_without_complete_exif_gps_has_unknown_gps_source(
    tmp_path: Path,
):
    class FakeMetadata:
        width = 640
        height = 480
        orientation = 1
        capture_datetime = None
        latitude = 47.2184
        longitude = None

    class FakeExifReader:
        def read(self, path: Path):
            return FakeMetadata()

    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"placeholder")

    analyzer = PhotoAnalyzer(exif_reader=FakeExifReader())
    photo = analyzer.analyze(image_path)

    assert photo.gps_source == GpsSource.UNKNOWN
    assert photo.exif_latitude is None
    assert photo.exif_longitude is None
