from dataclasses import replace
from datetime import datetime
from pathlib import Path
import sqlite3

import pytest

from photoalbum.app import ProjectService
from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.database.source_repository import SourceRepository
from photoalbum.models import Photo, PhotoUsage
from photoalbum.sources import ProjectSource, SourceAsset, PhotoMetadataPolicy
from photoalbum.app.project_scan_service import ProjectScanService
from tests.test_photo_sources import FakeRemoteSource


def test_same_path_is_independent_and_usage_sets_follow_source_activation(tmp_path):
    service = ProjectService()
    service.create(tmp_path / "album.sqlite")
    first, second = service.add_local_source(tmp_path), service.add_local_source(tmp_path)
    assert first.id != second.id
    repository = PhotoRepository(service._require_database())
    path = tmp_path / "shared.jpg"
    photos = [Photo(path, path.name, source_id=source.id, asset_id=str(path)) for source in (first, second)]
    for photo in photos:
        repository.save(photo)
    service.set_photo_caption(photos[0].identity, "Only first")
    service.set_manual_capture_datetime(photos[1].identity, datetime(2025, 1, 1))
    service.set_photo_usage(photos[0].identity, PhotoUsage.TEMPLATE_ONLY)
    assert repository.find_by_identity(photos[1].identity).caption is None
    assert repository.find_by_identity(photos[0].identity).capture_datetime is None
    assert len(service.list_photos()) == 2
    assert len(service.list_album_photos()) == 2
    assert [photo.identity for photo in service.list_body_photos()] == [photos[1].identity]
    service.set_photo_usage(photos[1].identity, PhotoUsage.OFF)
    assert len(service.list_photos()) == 2
    assert len(service.list_album_photos()) == 1
    assert service.list_body_photos() == []
    service.set_source_enabled(first.id, False)
    assert service.list_album_photos() == []
    assert len(repository.list_by_source(first.id)) == 1
    service.set_source_enabled(first.id, True)
    assert service.list_album_photos()[0].caption == "Only first"
    service.delete_source(first.id)
    assert repository.find_by_identity(photos[0].identity) is None
    assert repository.find_by_identity(photos[1].identity) is not None
    assert service._require_database().get_project_metadata("photo_source") is None
    service.close()


def test_refresh_isolated_status_and_policies_survive(tmp_path):
    service = ProjectService()
    service.create(tmp_path / "album.sqlite")
    sources = [ProjectSource(id=str(i), kind="fake", name=str(i), collection_id="album", collection_name=str(i)) for i in range(2)]
    providers = [FakeRemoteSource([SourceAsset(id="same", filename="same.jpg", capture_datetime=datetime(2025, 1, 1))]) for _ in sources]
    for source, provider in zip(sources, providers):
        service.change_photo_source(source, provider)
    service.set_photo_usage("0:same", PhotoUsage.TEMPLATE_ONLY)
    service.set_photo_caption("0:same", "Preserved")
    service.sync_photo_source("0")
    assert len(service.list_photos()) == 2
    assert service.find_photo_by_identity("0:same").usage == PhotoUsage.TEMPLATE_ONLY
    assert service.find_photo_by_identity("0:same").caption == "Preserved"
    policy = PhotoMetadataPolicy("filename", "exif", "none", False)
    service.set_photo_metadata_policy(policy, "0")
    assert service.get_photo_metadata_policy("1") != policy
    providers[0].assets = []
    service.sync_photo_source("0")
    assert [photo.identity for photo in service.list_photos()] == ["1:same"]
    assert service.get_photo_source_session("1") is providers[1]
    # A policy refresh must not resurrect assets absent from the snapshot.
    service.apply_photo_metadata_policy(source_id="0")
    assert [photo.identity for photo in service.list_photos()] == ["1:same"]
    service.close()


def test_local_scan_scopes_cache_missing_and_preserves_usage(tmp_path):
    from PIL import Image
    folder = tmp_path / "photos"
    folder.mkdir()
    path = folder / "2025-01-01.jpg"
    Image.new("RGB", (20, 20)).save(path)
    service = ProjectService()
    service.create(tmp_path / "album.sqlite")
    sources = [service.add_local_source(folder) for _ in range(2)]
    for source in sources:
        ProjectScanService().scan(project_path=service.project_path, source_directory=folder, source_id=source.id)
    assert len(service.list_photos()) == 2
    identity = f"{sources[0].id}:{path}"
    service.set_photo_usage(identity, PhotoUsage.OFF)
    service.set_photo_caption(identity, "Manual")
    Image.new("RGB", (30, 30)).save(path)
    ProjectScanService().scan(project_path=service.project_path, source_directory=folder, source_id=sources[0].id)
    assert service.find_photo_by_identity(identity).usage == PhotoUsage.OFF
    assert service.find_photo_by_identity(identity).caption == "Manual"
    empty = tmp_path / "empty"
    empty.mkdir()
    ProjectScanService().scan(project_path=service.project_path, source_directory=empty, source_id=sources[0].id)
    assert [photo.source_id for photo in service.list_photos()] == [sources[1].id]
    service.close()


def legacy_database(path):
    connection = sqlite3.connect(path)
    connection.executescript((Path(__file__).parent / "fixtures/v010_schema.sql").read_text())
    connection.execute("INSERT INTO project_metadata VALUES ('source_directory', '/photos')")
    connection.execute("INSERT INTO project_metadata VALUES ('recursive_scan', '1')")
    connection.execute("""INSERT INTO photos(path, filename, capture_datetime, date_source,
        original_capture_datetime, original_date_source, latitude, longitude, original_latitude,
        original_longitude, caption, location_text, location_selection_edited)
        VALUES('/photos/a.jpg', 'a.jpg', '2025-01-02T00:00:00', 'manual',
        '2024-01-01T00:00:00', 'exif', 48, 2, 48, 2, 'Caption', 'Manual place', 1)""")
    connection.commit()
    connection.close()


def test_real_published_schema_migrates_directly_and_preserves_user_state(tmp_path):
    path = tmp_path / "published.sqlite"
    legacy_database(path)
    database = ProjectDatabase(path)
    database.initialize()
    source = SourceRepository(database).list_all()[0]
    assert source.config == {"directory": "/photos", "recursive": True}
    photo = PhotoRepository(database).list_all()[0]
    assert photo.identity == "local:/photos/a.jpg"
    assert photo.usage == PhotoUsage.BODY
    assert photo.caption == "Caption" and photo.location_text == "Manual place"
    assert photo.manual_capture_datetime == datetime(2025, 1, 2)
    assert photo.metadata_candidates.date["exif"] == datetime(2024, 1, 1)
    assert photo.manual_location_data["address"] == "Manual place"
    assert database.get_project_metadata("source_directory") is None
    before = list(database.connection.iterdump())
    database.initialize()
    assert list(database.connection.iterdump()) == before
    database.close()


def test_migration_failure_rolls_back_entire_schema_and_source_collection(tmp_path, monkeypatch):
    path = tmp_path / "published.sqlite"
    legacy_database(path)
    database = ProjectDatabase(path)
    before = list(database.connection.iterdump())
    def fail():
        raise RuntimeError("injected failure")
    monkeypatch.setattr(database, "_create_photos_table", fail)
    with pytest.raises(RuntimeError, match="injected"):
        database.initialize()
    assert list(database.connection.iterdump()) == before
    database.close()
