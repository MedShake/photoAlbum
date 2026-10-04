from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

import pytest

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.models import DateSource, GpsSource, LocationSource, Photo
from photoalbum.sources import (
    ProjectSource,
    SourceAsset,
    SourceAssetCache,
    SourceCollection,
    SourceImporter,
)


class FakeRemoteSource:
    kind = "fake"

    def __init__(self, assets):
        self.assets = list(assets)
        self.thumbnail_fetches = []
        self.original_fetches = []

    def list_collections(self):
        return [SourceCollection("album", "Album", len(self.assets))]

    def list_assets(self, collection_id):
        assert collection_id == "album"
        return list(self.assets)

    def fetch_thumbnail(self, asset, destination):
        self.thumbnail_fetches.append(asset.id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(f"thumbnail:{asset.id}".encode())
        return destination

    def fetch_original(self, asset, destination):
        self.original_fetches.append(asset.id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(f"original:{asset.id}".encode())
        return destination

    def close(self):
        pass


def project_source():
    return ProjectSource(
        id="remote-1", kind="fake", name="Fake",
        collection_id="album", collection_name="Album",
    )


def test_remote_photo_has_identity_without_local_path():
    photo = Photo(
        path=None, filename="remote.jpg", source_id="remote-1", asset_id="42"
    )
    assert photo.identity == "remote-1:42"
    assert photo.path is None


def test_remote_photo_round_trip_without_local_path(tmp_path):
    database = ProjectDatabase(tmp_path / "album.photoalbum")
    database.initialize()
    repository = PhotoRepository(database)
    photo = Photo(
        path=None,
        filename="remote.jpg",
        source_id="remote-1",
        asset_id="42",
        imported_location_text="Paris, France",
        imported_caption="From Synology",
        source_metadata={"additional": {"thumbnail": {"cache_key": "42_1"}}},
    )
    repository.save(photo)
    loaded = repository.find_by_identity(photo.identity)
    assert loaded is not None
    assert loaded.path is None
    assert loaded.identity == photo.identity
    assert loaded.imported_location_text == "Paris, France"
    assert loaded.imported_caption == "From Synology"
    assert loaded.source_metadata == photo.source_metadata
    database.close()


def test_import_is_snapshot_and_only_fetches_thumbnails(tmp_path):
    database = ProjectDatabase(tmp_path / "album.photoalbum")
    database.initialize()
    repository = PhotoRepository(database)
    provider = FakeRemoteSource([
        SourceAsset(
            id="42", filename="remote.jpg",
            capture_datetime=datetime(2024, 7, 1, 12, 30),
            latitude=48.0, longitude=2.0,
            description="Provider description",
            location_text="Paris, France", revision="42_1",
        )
    ])
    result = SourceImporter(
        repository, SourceAssetCache(database.path)
    ).import_collection(project_source(), provider)
    assert result.added == 1
    assert result.missing == 0
    assert provider.thumbnail_fetches == ["42"]
    assert provider.original_fetches == []
    photo = result.photos[0]
    assert photo.path.read_bytes() == b"thumbnail:42"
    assert photo.date_source == DateSource.SOURCE
    assert photo.gps_source == GpsSource.SOURCE
    assert photo.source_capture_datetime == datetime(2024, 7, 1, 12, 30)
    assert photo.source_latitude == 48.0
    assert photo.source_longitude == 2.0
    assert photo.exif_capture_datetime is None
    assert photo.exif_latitude is None
    assert photo.exif_longitude is None
    database.close()


def test_refresh_preserves_editorial_changes_and_marks_missing_explicitly(tmp_path):
    database = ProjectDatabase(tmp_path / "album.photoalbum")
    database.initialize()
    repository = PhotoRepository(database)
    cache = SourceAssetCache(database.path)
    first = FakeRemoteSource([
        SourceAsset(id="1", filename="one.jpg", latitude=1, longitude=2),
        SourceAsset(id="2", filename="two.jpg"),
    ])
    SourceImporter(repository, cache).import_collection(project_source(), first)
    photo = repository.find_by_identity("remote-1:1")
    photo.caption = "My caption"
    photo.location_text = "My place"
    photo.location_selection_edited = True
    photo.latitude = 3
    photo.longitude = 4
    photo.location_source = LocationSource.MANUAL
    repository.save(photo)

    second = FakeRemoteSource([
        SourceAsset(
            id="1", filename="renamed.jpg", latitude=50, longitude=6,
            location_text="Provider place",
        )
    ])
    result = SourceImporter(repository, cache).import_collection(
        project_source(), second
    )
    loaded = repository.find_by_identity("remote-1:1")
    assert result.updated == 1
    assert result.missing == 1
    assert loaded.caption == "My caption"
    assert loaded.location_text == "My place"
    assert loaded.location_selection_edited is True
    assert (loaded.latitude, loaded.longitude) == (3, 4)
    assert (loaded.original_latitude, loaded.original_longitude) == (50, 6)
    assert loaded.imported_location_text == "Provider place"
    assert [p.identity for p in repository.list_all()] == ["remote-1:1"]
    database.close()


def test_original_is_fetched_only_when_materialized(tmp_path):
    project_path = tmp_path / "album.photoalbum"
    provider = FakeRemoteSource([])
    cache = SourceAssetCache(project_path)
    photo = Photo(
        path=None, filename="remote.jpg", source_id="remote-1", asset_id="42"
    )
    thumbnail = cache.materialize(photo, provider, quality="thumbnail")
    photo.path = thumbnail
    assert thumbnail.read_bytes() == b"thumbnail:42"
    assert provider.original_fetches == []
    original = cache.materialize(photo, provider, quality="original")
    assert original == thumbnail
    assert original.read_bytes() == b"original:42"
    assert provider.original_fetches == ["42"]


def test_project_source_serialization_excludes_credentials():
    source = ProjectSource(
        id="synology-1", kind="synology-photos", name="NAS",
        collection_id="12", collection_name="Summer",
        config={"base_url": "https://nas.example", "username": "alice"},
    )
    encoded = source.to_json()
    assert "password" not in encoded
    assert ProjectSource.from_json(encoded) == source


@pytest.mark.parametrize(
    "config",
    [
        {"password": "value"},
        {"passwd": "value"},
        {"credentials": {"username": "alice"}},
        {"nested": {"access_token": "value"}},
        {"SynoToken": "value"},
        {"_sid": "value"},
        {"otp_code": "value"},
    ],
)
def test_project_source_refuses_sensitive_configuration(config):
    source = ProjectSource(
        id="remote", kind="fake", name="Remote",
        collection_id="album", collection_name="Album", config=config,
    )
    with pytest.raises(ValueError, match="Sensitive project source"):
        source.to_json()


def test_project_source_refuses_sensitive_configuration_when_loading():
    encoded = json.dumps({
        "schema_version": 1,
        "id": "remote",
        "kind": "fake",
        "name": "Remote",
        "collection_id": "album",
        "collection_name": "Album",
        "config": {"nested": [{"client_secret": "value"}]},
    })
    with pytest.raises(ValueError, match=r"config.nested\[0\].client_secret"):
        ProjectSource.from_json(encoded)


def test_metadata_candidates_roundtrip(tmp_path):
    from datetime import datetime

    from photoalbum.database import PhotoRepository, ProjectDatabase
    from photoalbum.models import DateSource, GpsSource, LocationSource, Photo

    database = ProjectDatabase(tmp_path / "candidates.photoalbum")
    database.initialize()
    repository = PhotoRepository(database)

    exif_date = datetime(2024, 4, 5, 6, 7, 8)
    source_date = datetime(2024, 4, 5, 6, 7, 9)

    photo = Photo(
        path=tmp_path / "photo.jpg",
        filename="photo.jpg",
        capture_datetime=source_date,
        date_source=DateSource.SOURCE,
        latitude=48.1,
        longitude=2.3,
        gps_source=GpsSource.SOURCE,
        exif_capture_datetime=exif_date,
        source_capture_datetime=source_date,
        exif_latitude=48.0,
        exif_longitude=2.0,
        source_latitude=48.1,
        source_longitude=2.3,
        source_location_data={
            "provider": "synology",
            "city": "Paris",
            "components": [
                {"key": "city", "value": "Paris"},
                {"key": "country", "value": "France"},
            ],
        },
        geocoded_location_data={
            "provider": "nominatim",
            "place_name": "Tour Eiffel",
            "city": "Paris",
        },
        place_name="Paris",
        city="Paris",
        location_source=LocationSource.SOURCE,
    )

    repository.save(photo)
    loaded = repository.find_by_path(photo.path)

    assert loaded is not None
    assert loaded.date_source == DateSource.SOURCE
    assert loaded.gps_source == GpsSource.SOURCE
    assert loaded.location_source == LocationSource.SOURCE

    assert loaded.exif_capture_datetime == exif_date
    assert loaded.source_capture_datetime == source_date
    assert loaded.exif_latitude == 48.0
    assert loaded.exif_longitude == 2.0
    assert loaded.source_latitude == 48.1
    assert loaded.source_longitude == 2.3

    assert loaded.source_location_data == photo.source_location_data
    assert loaded.geocoded_location_data == photo.geocoded_location_data

    database.close()

def test_import_uses_structured_provider_location_as_effective_candidate(tmp_path):
    database = ProjectDatabase(tmp_path / "structured-location.photoalbum")
    database.initialize()
    repository = PhotoRepository(database)

    structured_location = {
        "provider": "fake",
        "place_name": "Château Example",
        "city": "Example City",
        "address": "Example City, France",
        "components": [
            {"key": "city", "value": "Example City"},
            {"key": "country", "value": "France"},
        ],
        "raw": {"city": "Example City", "country": "France"},
    }

    provider = FakeRemoteSource([
        SourceAsset(
            id="42",
            filename="remote.jpg",
            location_text="Example City, France",
            structured_location=structured_location,
        )
    ])

    result = SourceImporter(
        repository,
        SourceAssetCache(database.path),
    ).import_collection(project_source(), provider)

    photo = result.photos[0]
    assert photo.source_location_data == structured_location
    assert photo.place_name == "Château Example"
    assert photo.city == "Example City"
    assert photo.address == "Example City, France"
    assert photo.location_source == LocationSource.SOURCE

    loaded = repository.find_by_identity(photo.identity)
    assert loaded is not None
    assert loaded.source_location_data == structured_location
    assert loaded.city == "Example City"
    assert loaded.location_source == LocationSource.SOURCE

    database.close()

