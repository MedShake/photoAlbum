from pathlib import Path
import sqlite3

from photoalbum.database import ProjectDatabase
from photoalbum.database import PhotoRepository
from photoalbum.models import Photo


def test_project_database_creates_file(tmp_path: Path):
    project_path = tmp_path / "family-2025.photoalbum"

    database = ProjectDatabase(project_path)
    database.initialize()

    assert project_path.exists()

    database.close()


def test_project_database_has_schema_version(tmp_path: Path):
    project_path = tmp_path / "family-2025.photoalbum"

    database = ProjectDatabase(project_path)
    database.initialize()

    assert (
        database.connection.execute("SELECT version FROM schema_version").fetchone()["version"]
        == ProjectDatabase.CURRENT_SCHEMA_VERSION
    )

    database.close()


def test_project_metadata_can_be_saved_and_loaded(
    tmp_path: Path,
):
    project_path = tmp_path / "family-2025.photoalbum"

    database = ProjectDatabase(project_path)
    database.initialize()

    database.set_project_metadata(
        "project_name",
        "Family 2025",
    )

    assert (
        database.get_project_metadata("project_name")
        == "Family 2025"
    )

    database.close()


def test_unknown_project_metadata_returns_none(
    tmp_path: Path,
):
    project_path = tmp_path / "family-2025.photoalbum"

    database = ProjectDatabase(project_path)
    database.initialize()

    assert (
        database.get_project_metadata("unknown")
        is None
    )

    database.close()




def test_initialize_is_idempotent(tmp_path: Path):
    project_path = tmp_path / "family-2025.photoalbum"

    database = ProjectDatabase(project_path)

    database.initialize()
    database.initialize()

    assert (
        database.connection.execute("SELECT version FROM schema_version").fetchone()["version"]
        == ProjectDatabase.CURRENT_SCHEMA_VERSION
    )

    database.close()


def test_existing_project_keeps_its_metadata(
    tmp_path: Path,
):
    project_path = tmp_path / "family-2025.photoalbum"

    database = ProjectDatabase(project_path)
    database.initialize()

    database.set_project_metadata(
        "project_name",
        "Family 2025",
    )

    database.close()

    reopened = ProjectDatabase(project_path)
    reopened.initialize()

    assert (
        reopened.get_project_metadata("project_name")
        == "Family 2025"
    )

    reopened.close()


def test_v1_project_migrates_path_to_stable_asset_identity(tmp_path: Path):
    project_path = tmp_path / "legacy.photoalbum"
    database = ProjectDatabase(project_path)
    database.initialize()
    path = (tmp_path / "photo.jpg").resolve()
    PhotoRepository(database).save(Photo(path=path, filename=path.name))
    database.close()

    connection = sqlite3.connect(project_path)
    new_columns = {
        "asset_key", "source_id", "asset_id", "imported_location_text",
        "imported_caption", "source_metadata",
    }
    columns = [
        row[1]
        for row in connection.execute("PRAGMA table_info(photos)")
        if row[1] not in new_columns
    ]
    projection = ", ".join(columns)
    connection.execute(f"CREATE TABLE legacy_photos AS SELECT {projection} FROM photos")
    connection.execute("DROP TABLE photos")
    connection.execute("ALTER TABLE legacy_photos RENAME TO photos")
    connection.execute("UPDATE schema_version SET version = 1")
    connection.commit()
    connection.close()

    migrated = ProjectDatabase(project_path)
    migrated.initialize()
    loaded = PhotoRepository(migrated).find_by_path(path)
    assert loaded is not None
    assert loaded.identity == f"local:{path}"
    assert loaded.path == path
    assert migrated.connection.execute(
        "SELECT version FROM schema_version"
    ).fetchone()["version"] == ProjectDatabase.CURRENT_SCHEMA_VERSION
    migrated.close()

def test_v2_project_migrates_metadata_candidates_without_changing_effective_data(
    tmp_path: Path,
):
    import json
    from datetime import datetime

    from photoalbum.database import PhotoRepository, ProjectDatabase
    from photoalbum.models import (
        DateSource,
        LocationComponent,
        LocationSource,
        Photo,
    )

    project_path = tmp_path / "v2-metadata.photoalbum"
    photo_path = tmp_path / "photo.jpg"

    database = ProjectDatabase(project_path)
    database.initialize()

    original_date = datetime(2024, 5, 6, 12, 34, 56)
    raw_location = {
        "address": {
            "city": "Orvault",
            "state": "Pays de la Loire",
            "country": "France",
        }
    }

    photo = Photo(
        path=photo_path,
        filename=photo_path.name,
        capture_datetime=original_date,
        date_source=DateSource.EXIF,
        latitude=47.2701,
        longitude=-1.6212,
        original_capture_datetime=original_date,
        original_date_source=DateSource.EXIF,
        original_latitude=47.2701,
        original_longitude=-1.6212,
        place_name="Plaisance",
        city="Orvault",
        address="Orvault, France",
        raw_location_data=raw_location,
        location_source=LocationSource.GEOCODING,
        selected_location_components=(
            LocationComponent(key="city", value="Orvault"),
            LocationComponent(key="country", value="France"),
        ),
        location_text="Orvault, France",
        location_selection_edited=True,
        caption="Photo conservée",
    )
    PhotoRepository(database).save(photo)

    v3_columns = (
        "exif_capture_datetime",
        "source_capture_datetime",
        "exif_latitude",
        "exif_longitude",
        "source_latitude",
        "source_longitude",
        "gps_source",
        "source_location_data",
        "geocoded_location_data",
    )
    for column in v3_columns:
        database.connection.execute(
            f"ALTER TABLE photos DROP COLUMN {column}"
        )

    database.connection.execute(
        "UPDATE schema_version SET version = 2"
    )
    database.connection.commit()
    database.close()

    migrated = ProjectDatabase(project_path)
    migrated.initialize()

    row = migrated.connection.execute(
        "SELECT * FROM photos WHERE path = ?",
        (str(photo_path),),
    ).fetchone()

    assert row["capture_datetime"] == original_date.isoformat()
    assert row["date_source"] == DateSource.EXIF.value
    assert row["latitude"] == 47.2701
    assert row["longitude"] == -1.6212
    assert row["place_name"] == "Plaisance"
    assert row["city"] == "Orvault"
    assert row["address"] == "Orvault, France"
    assert json.loads(row["raw_location_data"]) == raw_location
    assert row["location_source"] == LocationSource.GEOCODING.value
    assert row["location_text"] == "Orvault, France"
    assert row["location_selection_edited"] == 1
    assert row["caption"] == "Photo conservée"

    assert row["exif_capture_datetime"] == original_date.isoformat()
    assert row["exif_latitude"] == 47.2701
    assert row["exif_longitude"] == -1.6212
    assert row["source_capture_datetime"] is None
    assert row["source_latitude"] is None
    assert row["source_longitude"] is None
    assert row["gps_source"] == "exif"
    assert row["source_location_data"] is None

    geocoded = json.loads(row["geocoded_location_data"])
    assert geocoded["provider"] == "nominatim"
    assert geocoded["latitude"] == 47.2701
    assert geocoded["longitude"] == -1.6212
    assert geocoded["place_name"] == "Plaisance"
    assert geocoded["city"] == "Orvault"
    assert geocoded["address"] == "Orvault, France"
    assert geocoded["raw"] == raw_location

    loaded = PhotoRepository(migrated).find_by_path(photo_path)
    assert loaded is not None
    assert loaded.capture_datetime == original_date
    assert loaded.latitude == 47.2701
    assert loaded.longitude == -1.6212
    assert loaded.location_text == "Orvault, France"
    assert loaded.caption == "Photo conservée"

    assert migrated.connection.execute(
        "SELECT version FROM schema_version"
    ).fetchone()["version"] == 3

    migrated.close()


def test_v2_remote_project_migrates_provider_candidates(tmp_path: Path):
    from datetime import datetime

    from photoalbum.database import PhotoRepository, ProjectDatabase
    from photoalbum.models import DateSource, Photo

    project_path = tmp_path / "v2-remote.photoalbum"
    cached_path = tmp_path / "remote-thumb.jpg"
    provider_date = datetime(2025, 2, 3, 10, 20, 30)

    database = ProjectDatabase(project_path)
    database.initialize()

    PhotoRepository(database).save(
        Photo(
            path=cached_path,
            filename="remote.jpg",
            source_id="synology-test",
            asset_id="42",
            capture_datetime=provider_date,
            date_source=DateSource.EXIF,
            latitude=48.1,
            longitude=2.3,
            original_capture_datetime=provider_date,
            original_date_source=DateSource.EXIF,
            original_latitude=48.1,
            original_longitude=2.3,
        )
    )

    v3_columns = (
        "exif_capture_datetime",
        "source_capture_datetime",
        "exif_latitude",
        "exif_longitude",
        "source_latitude",
        "source_longitude",
        "gps_source",
        "source_location_data",
        "geocoded_location_data",
    )
    for column in v3_columns:
        database.connection.execute(
            f"ALTER TABLE photos DROP COLUMN {column}"
        )

    database.connection.execute(
        "UPDATE schema_version SET version = 2"
    )
    database.connection.commit()
    database.close()

    migrated = ProjectDatabase(project_path)
    migrated.initialize()

    row = migrated.connection.execute(
        "SELECT * FROM photos WHERE asset_key = ?",
        ("synology-test:42",),
    ).fetchone()

    assert row["capture_datetime"] == provider_date.isoformat()
    assert row["latitude"] == 48.1
    assert row["longitude"] == 2.3

    assert row["source_capture_datetime"] == provider_date.isoformat()
    assert row["source_latitude"] == 48.1
    assert row["source_longitude"] == 2.3

    assert row["exif_capture_datetime"] is None
    assert row["exif_latitude"] is None
    assert row["exif_longitude"] is None
    assert row["gps_source"] == "source"

    migrated.close()


def test_schema_v3_initialization_is_idempotent(tmp_path: Path):
    from photoalbum.database import ProjectDatabase

    project_path = tmp_path / "idempotent.photoalbum"

    database = ProjectDatabase(project_path)
    database.initialize()

    first_columns = tuple(
        row["name"]
        for row in database.connection.execute(
            "PRAGMA table_info(photos)"
        )
    )

    database.initialize()

    second_columns = tuple(
        row["name"]
        for row in database.connection.execute(
            "PRAGMA table_info(photos)"
        )
    )

    assert first_columns == second_columns
    assert len(first_columns) == len(set(first_columns))
    assert database.connection.execute(
        "SELECT version FROM schema_version"
    ).fetchone()["version"] == 3

    database.close()

