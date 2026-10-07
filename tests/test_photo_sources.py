from __future__ import annotations
from photoalbum.gui.workers import SourceSyncWorker

from datetime import datetime
from pathlib import Path
import json

import pytest

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.models import (
    DateSource,
    GpsCandidate,
    GpsSource,
    LocationComponent,
    LocationSource,
    MetadataCandidates,
    Photo,
)
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


def test_provider_can_import_multiple_real_candidates_per_dimension(tmp_path):
    database = ProjectDatabase(tmp_path / "multiple.photoalbum")
    database.initialize()
    repository = PhotoRepository(database)
    provider_date = datetime(2024, 7, 1, 12, 30)
    exif_date = datetime(2024, 7, 1, 12, 29)
    provider = FakeRemoteSource([
        SourceAsset(
            id="42",
            filename="IMG_20240701_123100.jpg",
            candidates=MetadataCandidates(
                date={"provider": provider_date, "exif": exif_date},
                gps={
                    "provider": GpsCandidate(48.0, 2.0),
                    "exif": GpsCandidate(47.0, -1.0),
                },
            ),
        )
    ])

    SourceImporter(repository, SourceAssetCache(database.path)).import_collection(
        project_source(), provider
    )
    photo = repository.find_by_identity("remote-1:42")

    assert photo is not None
    assert photo.metadata_candidates.date["provider"] == provider_date
    assert photo.metadata_candidates.date["exif"] == exif_date
    assert "filename" in photo.metadata_candidates.date
    assert photo.metadata_candidates.gps["provider"] == GpsCandidate(48.0, 2.0)
    assert photo.metadata_candidates.gps["exif"] == GpsCandidate(47.0, -1.0)
    database.close()


def test_provider_only_candidate_does_not_invent_exif(tmp_path):
    database = ProjectDatabase(tmp_path / "provider-only.photoalbum")
    database.initialize()
    repository = PhotoRepository(database)
    provider = FakeRemoteSource([
        SourceAsset(
            id="42",
            filename="plain.jpg",
            candidates=MetadataCandidates(
                date={"provider": datetime(2024, 7, 1)},
                gps={"provider": GpsCandidate(48.0, 2.0)},
            ),
        )
    ])
    SourceImporter(repository, SourceAssetCache(database.path)).import_collection(
        project_source(), provider
    )
    photo = repository.find_by_identity("remote-1:42")
    assert photo is not None
    assert "exif" not in photo.metadata_candidates.date
    assert "exif" not in photo.metadata_candidates.gps
    assert photo.exif_capture_datetime is None
    assert photo.exif_latitude is None
    database.close()


def test_resync_preserves_independent_manual_values_and_editorial_caption(tmp_path):
    database = ProjectDatabase(tmp_path / "manual.photoalbum")
    database.initialize()
    repository = PhotoRepository(database)
    cache = SourceAssetCache(database.path)
    first = FakeRemoteSource([
        SourceAsset(
            id="1",
            filename="one.jpg",
            capture_datetime=datetime(2020, 1, 1),
            latitude=48.0,
            longitude=2.0,
            structured_location={"city": "Paris", "address": "Paris"},
            description="Provider caption",
        )
    ])
    SourceImporter(repository, cache).import_collection(project_source(), first)
    path = repository.find_by_identity("remote-1:1").path
    manual_date = datetime(2025, 2, 3, 4, 5)
    repository.set_manual_capture_datetime(path, manual_date)
    repository.set_manual_gps(path, 45.0, 4.0)
    repository.set_editorial_location(
        path,
        components=(LocationComponent("city", "Lyon"),),
        location_text="Lyon, France",
    )
    repository.set_caption(path, "Editorial caption")

    second = FakeRemoteSource([
        SourceAsset(
            id="1",
            filename="one.jpg",
            capture_datetime=datetime(2030, 1, 1),
            latitude=50.0,
            longitude=6.0,
            structured_location={"city": "Brussels", "address": "Brussels"},
            description="Changed provider caption",
        )
    ])
    SourceImporter(repository, cache).import_collection(project_source(), second)
    loaded = repository.find_by_identity("remote-1:1")

    assert loaded.capture_datetime == manual_date
    assert loaded.date_source == DateSource.MANUAL
    assert (loaded.latitude, loaded.longitude) == (45.0, 4.0)
    assert loaded.gps_source == GpsSource.MANUAL
    assert loaded.address == "Lyon, France"
    assert loaded.location_source == LocationSource.MANUAL
    assert loaded.caption == "Editorial caption"
    assert loaded.imported_caption == "Changed provider caption"
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
    photo.gps_source = GpsSource.MANUAL
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
    assert original != thumbnail
    assert thumbnail.read_bytes() == b"thumbnail:42"
    assert original.read_bytes() == b"original:42"
    assert provider.original_fetches == ["42"]



def test_materialize_stages_outside_digest_directory(tmp_path):
    project_path = tmp_path / "album.photoalbum"
    cache = SourceAssetCache(project_path)
    photo = Photo(
        path=None, filename="remote.jpg", source_id="remote-1", asset_id="42"
    )

    destinations = []

    class CapturingRemoteSource(FakeRemoteSource):
        def fetch_thumbnail(self, asset, destination):
            destinations.append(destination)
            return super().fetch_thumbnail(asset, destination)

    provider = CapturingRemoteSource([])
    cached = cache.materialize(photo, provider, quality="thumbnail")

    assert cached == cache.path_for(photo, "thumbnail")
    assert destinations[0].parent == cached.parent.parent
    assert destinations[0].parent.name == "thumbnail"
    assert destinations[0].parent != cached.parent
    assert cached.read_bytes() == b"thumbnail:42"

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


def test_source_import_reports_each_processed_asset(tmp_path):
    database = ProjectDatabase(
        tmp_path / "progress.photoalbum"
    )
    database.initialize()

    provider = FakeRemoteSource([
        SourceAsset(id="1", filename="one.jpg"),
        SourceAsset(id="2", filename="two.jpg"),
        SourceAsset(id="3", filename="three.jpg"),
    ])

    progress = []

    SourceImporter(
        PhotoRepository(database),
        SourceAssetCache(database.path),
    ).import_collection(
        project_source(),
        provider,
        on_progress=lambda current, total: progress.append(
            (current, total)
        ),
    )

    assert progress == [
        (1, 3),
        (2, 3),
        (3, 3),
    ]

    database.close()


def test_source_sync_worker_uses_project_file_and_forwards_progress(tmp_path):
    project_path = tmp_path / "worker-progress.photoalbum"

    database = ProjectDatabase(project_path)
    database.initialize()
    database.close()

    provider = FakeRemoteSource([
        SourceAsset(id="1", filename="one.jpg"),
        SourceAsset(id="2", filename="two.jpg"),
    ])

    worker = SourceSyncWorker(
        project_path=project_path,
        source=project_source(),
        provider=provider,
    )

    progress = []
    completed = []
    failed = []

    worker.progress.connect(
        lambda current, total: progress.append(
            (current, total)
        )
    )
    worker.completed.connect(completed.append)
    worker.failed.connect(failed.append)

    worker.run()

    assert failed == []
    assert progress == [
        (0, 0),
        (1, 2),
        (2, 2),
    ]
    assert len(completed) == 1
    assert len(completed[0].photos) == 2

    reopened = ProjectDatabase(project_path)
    reopened.initialize()
    assert len(PhotoRepository(reopened).list_all()) == 2
    reopened.close()
