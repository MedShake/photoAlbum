from datetime import datetime
from pathlib import Path

from photoalbum.database import Database, PhotoRepository
from photoalbum.models import DateSource, Photo


def create_repository(tmp_path: Path) -> tuple[Database, PhotoRepository]:
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()

    repository = PhotoRepository(database)

    return database, repository


def test_save_and_load_photo(tmp_path: Path):
    database, repository = create_repository(tmp_path)

    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        width=1920,
        height=1080,
        orientation=1,
        capture_datetime=datetime(2025, 6, 15, 14, 30, 45),
        date_source=DateSource.EXIF,
        latitude=46.5,
        longitude=-1.25,
        place_name="Example Place",
        city="Example City",
        address="Example Address",
    )

    repository.save(photo)

    loaded = repository.find_by_path(photo.path)

    assert loaded is not None
    assert loaded.path == photo.path
    assert loaded.filename == photo.filename
    assert loaded.width == 1920
    assert loaded.height == 1080
    assert loaded.capture_datetime == datetime(
        2025,
        6,
        15,
        14,
        30,
        45,
    )
    assert loaded.date_source == DateSource.EXIF
    assert loaded.latitude == 46.5
    assert loaded.longitude == -1.25
    assert loaded.city == "Example City"

    database.close()


def test_save_updates_existing_photo(tmp_path: Path):
    database, repository = create_repository(tmp_path)

    path = Path("/photos/example.jpg")

    original = Photo(
        path=path,
        filename="example.jpg",
        capture_datetime=datetime(2025, 6, 15),
        date_source=DateSource.FILENAME,
    )

    repository.save(original)

    updated = Photo(
        path=path,
        filename="example.jpg",
        capture_datetime=datetime(2025, 6, 16, 12, 0),
        date_source=DateSource.MANUAL,
    )

    repository.save(updated)

    loaded = repository.find_by_path(path)

    assert loaded is not None
    assert loaded.capture_datetime == datetime(
        2025,
        6,
        16,
        12,
        0,
    )
    assert loaded.date_source == DateSource.MANUAL

    database.close()


def test_find_unknown_photo_returns_none(tmp_path: Path):
    database, repository = create_repository(tmp_path)

    loaded = repository.find_by_path(
        Path("/photos/missing.jpg")
    )

    assert loaded is None

    database.close()


def test_list_all_returns_photos(tmp_path: Path):
    database, repository = create_repository(tmp_path)

    repository.save(
        Photo(
            path=Path("/photos/b.jpg"),
            filename="b.jpg",
            capture_datetime=datetime(2025, 2, 1),
            date_source=DateSource.FILENAME,
        )
    )

    repository.save(
        Photo(
            path=Path("/photos/a.jpg"),
            filename="a.jpg",
            capture_datetime=datetime(2025, 1, 1),
            date_source=DateSource.FILENAME,
        )
    )

    photos = repository.list_all()

    assert [photo.filename for photo in photos] == [
        "a.jpg",
        "b.jpg",
    ]

    database.close()

def test_repository_preserves_file_information(tmp_path: Path):
    database, repository = create_repository(tmp_path)

    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        file_size=123456,
        modified_time_ns=987654321,
        content_hash="example-hash",
    )

    repository.save(photo)

    loaded = repository.find_by_path(photo.path)

    assert loaded is not None
    assert loaded.file_size == 123456
    assert loaded.modified_time_ns == 987654321
    assert loaded.content_hash == "example-hash"

    database.close()

def test_manual_capture_datetime_can_be_set(
    tmp_path: Path,
):
    database, repository = create_repository(tmp_path)

    path = Path("/photos/holiday.jpg")

    repository.save(
        Photo(
            path=path,
            filename="holiday.jpg",
        )
    )

    repository.set_manual_capture_datetime(
        path,
        datetime(2025, 7, 14, 18, 30),
    )

    loaded = repository.find_by_path(path)

    assert loaded is not None
    assert loaded.capture_datetime == datetime(
        2025,
        7,
        14,
        18,
        30,
    )
    assert loaded.date_source == DateSource.MANUAL
    assert loaded.is_date_anomaly is False

    database.close()


def test_manual_capture_datetime_requires_registered_photo(
    tmp_path: Path,
):
    database, repository = create_repository(tmp_path)

    missing = Path("/photos/missing.jpg")

    try:
        repository.set_manual_capture_datetime(
            missing,
            datetime(2025, 1, 1),
        )
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError")

    database.close()