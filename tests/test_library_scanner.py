from datetime import datetime
from pathlib import Path

from PIL import Image

from photoalbum.scanner import LibraryScanner


def create_image(path: Path) -> None:
    image = Image.new("RGB", (800, 600))
    image.save(path)


def create_image_with_exif_date(
    path: Path,
    value: str,
) -> None:
    image = Image.new("RGB", (800, 600))

    exif = Image.Exif()
    exif[36867] = value

    image.save(path, exif=exif)


def test_library_scanner_analyzes_photos(tmp_path: Path):
    create_image(
        tmp_path / "2025-06-15.jpg"
    )

    scanner = LibraryScanner()
    result = scanner.scan(tmp_path)

    assert result.total_photos == 1
    assert len(result.photos) == 1
    assert len(result.date_anomalies) == 0
    assert len(result.errors) == 0


def test_library_scanner_separates_date_anomalies(
    tmp_path: Path,
):
    create_image(
        tmp_path / "2025-06-15.jpg"
    )
    create_image(
        tmp_path / "holiday.jpg"
    )

    scanner = LibraryScanner()
    result = scanner.scan(tmp_path)

    assert result.total_photos == 2
    assert len(result.photos) == 1
    assert len(result.date_anomalies) == 1

    assert result.date_anomalies[0].filename == "holiday.jpg"


def test_library_scanner_sorts_photos_chronologically(
    tmp_path: Path,
):
    create_image(
        tmp_path / "2025-08-20.jpg"
    )
    create_image(
        tmp_path / "2025-01-05.jpg"
    )
    create_image(
        tmp_path / "2025-04-10.jpg"
    )

    scanner = LibraryScanner()
    result = scanner.scan(tmp_path)

    assert [
        photo.capture_datetime
        for photo in result.photos
    ] == [
        datetime(2025, 1, 5),
        datetime(2025, 4, 10),
        datetime(2025, 8, 20),
    ]


def test_exif_date_has_priority_over_filename(
    tmp_path: Path,
):
    image_path = tmp_path / "2025-08-20.jpg"

    create_image_with_exif_date(
        image_path,
        "2024:12:25 14:30:00",
    )

    scanner = LibraryScanner()
    result = scanner.scan(tmp_path)

    assert result.photos[0].capture_datetime == datetime(
        2024,
        12,
        25,
        14,
        30,
    )


def test_library_scanner_supports_recursive_scan(
    tmp_path: Path,
):
    subdirectory = tmp_path / "holiday"
    subdirectory.mkdir()

    create_image(
        tmp_path / "2025-01-01.jpg"
    )
    create_image(
        subdirectory / "2025-02-01.jpg"
    )

    scanner = LibraryScanner()

    non_recursive = scanner.scan(
        tmp_path,
        recursive=False,
    )

    recursive = scanner.scan(
        tmp_path,
        recursive=True,
    )

    assert non_recursive.total_photos == 1
    assert recursive.total_photos == 2


def test_invalid_image_is_reported_as_error(
    tmp_path: Path,
):
    invalid_image = tmp_path / "2025-01-01.jpg"
    invalid_image.write_text(
        "This is not an image.",
        encoding="utf-8",
    )

    scanner = LibraryScanner()
    result = scanner.scan(tmp_path)

    assert result.total_photos == 0
    assert len(result.errors) == 1
    assert result.errors[0].path == invalid_image
    assert result.errors[0].message

from photoalbum.database import Database, PhotoRepository
from photoalbum.models import DateSource, Photo


def create_cached_scanner(
    tmp_path: Path,
) -> tuple[Database, PhotoRepository, LibraryScanner]:
    database = Database(tmp_path / "library.sqlite3")
    database.initialize()

    repository = PhotoRepository(database)

    scanner = LibraryScanner(
        photo_repository=repository,
    )

    return database, repository, scanner


def test_library_scanner_saves_analyzed_photo(
    tmp_path: Path,
):
    database, repository, scanner = create_cached_scanner(
        tmp_path
    )

    image_path = tmp_path / "2025-06-15.jpg"
    create_image(image_path)

    result = scanner.scan(tmp_path)

    cached = repository.find_by_path(image_path)

    assert result.total_photos == 1
    assert cached is not None
    assert cached.capture_datetime == datetime(2025, 6, 15)

    database.close()


def test_library_scanner_reuses_cached_photo(
    tmp_path: Path,
):
    database, repository, scanner = create_cached_scanner(
        tmp_path
    )

    image_path = tmp_path / "holiday.jpg"
    create_image(image_path)

    file_stat = image_path.stat()

    repository.save(
        Photo(
            path=image_path,
            filename=image_path.name,
            file_size=file_stat.st_size,
            modified_time_ns=file_stat.st_mtime_ns,
            capture_datetime=datetime(2020, 1, 2, 12, 30),
            date_source=DateSource.MANUAL,
        )
    )

    result = scanner.scan(tmp_path)

    assert len(result.photos) == 1
    assert result.photos[0].capture_datetime == datetime(
        2020,
        1,
        2,
        12,
        30,
    )
    assert result.photos[0].date_source == DateSource.MANUAL

    database.close()


def test_library_scanner_reanalyzes_modified_photo(
    tmp_path: Path,
):
    database, repository, scanner = create_cached_scanner(
        tmp_path
    )

    image_path = tmp_path / "2025-06-15.jpg"
    create_image(image_path)

    repository.save(
        Photo(
            path=image_path,
            filename=image_path.name,
            file_size=1,
            modified_time_ns=1,
            capture_datetime=datetime(2000, 1, 1),
            date_source=DateSource.MANUAL,
        )
    )

    result = scanner.scan(tmp_path)

    assert len(result.photos) == 1
    assert result.photos[0].capture_datetime == datetime(
        2025,
        6,
        15,
    )
    assert result.photos[0].date_source == DateSource.FILENAME

    cached = repository.find_by_path(image_path)

    assert cached is not None
    assert cached.capture_datetime == datetime(2025, 6, 15)

    database.close()


def test_library_scanner_caches_date_anomalies(
    tmp_path: Path,
):
    database, repository, scanner = create_cached_scanner(
        tmp_path
    )

    image_path = tmp_path / "holiday.jpg"
    create_image(image_path)

    first_result = scanner.scan(tmp_path)

    assert len(first_result.date_anomalies) == 1

    cached = repository.find_by_path(image_path)

    assert cached is not None
    assert cached.date_source == DateSource.UNKNOWN

    second_result = scanner.scan(tmp_path)

    assert len(second_result.date_anomalies) == 1

    database.close()

    