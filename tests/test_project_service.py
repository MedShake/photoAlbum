from pathlib import Path

import pytest

from photoalbum.app import ProjectService
from photoalbum.sources import ProjectSource, SourceAsset

from photoalbum.album import (
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerSettings,
    PhotoPageSettings,
)

def test_create_project(tmp_path: Path):
    project_path = tmp_path / "album.photoalbum"

    service = ProjectService()
    service.create(project_path)

    assert service.is_open is True
    assert service.project_path == project_path.resolve()
    assert project_path.exists()

    service.close()


def test_open_existing_project(tmp_path: Path):
    project_path = tmp_path / "album.photoalbum"

    first_service = ProjectService()
    first_service.create(project_path)
    first_service.close()

    service = ProjectService()
    service.open(project_path)

    assert service.is_open is True
    assert service.project_path == project_path.resolve()

    service.close()


def test_open_missing_project_fails(tmp_path: Path):
    service = ProjectService()

    with pytest.raises(FileNotFoundError):
        service.open(tmp_path / "missing.photoalbum")


def test_source_directory_is_persisted(tmp_path: Path):
    project_path = tmp_path / "album.photoalbum"
    source_path = tmp_path / "photos"
    source_path.mkdir()

    service = ProjectService()
    service.create(project_path)
    service.set_source_directory(source_path)
    service.close()

    reopened = ProjectService()
    reopened.open(project_path)

    assert (
        reopened.get_source_directory()
        == source_path.resolve()
    )

    reopened.close()


def test_recursive_scan_is_persisted(tmp_path: Path):
    project_path = tmp_path / "album.photoalbum"

    service = ProjectService()
    service.create(project_path)
    service.set_photo_source(ProjectSource(id="local", kind="local", name="Local",
        collection_id="photos", collection_name="Photos", config={"directory": str(tmp_path / "photos")}))
    service.set_recursive_scan(True)
    service.close()

    reopened = ProjectService()
    reopened.open(project_path)

    assert reopened.get_recursive_scan() is True

    reopened.close()


def test_closed_project_rejects_metadata_access():
    service = ProjectService()

    with pytest.raises(RuntimeError):
        service.get_source_directory()

def create_album_settings() -> AlbumStructureSettings:
    return AlbumStructureSettings(
        covers={
            position: CoverSettings(
                position=position,
                template_id="cover",
            )
            for position in CoverPosition
        },
        day_dividers=DividerSettings(enabled=False, template_id="day-divider-simple"),
        month_dividers=DividerSettings(
            enabled=True,
            template_id="month",
        ),
        year_dividers=DividerSettings(
            enabled=False,
            template_id="year",
        ),
        photo_pages=PhotoPageSettings(
            template_id="photo-page-2",
        ),
    )


def test_album_settings_are_persisted(
    tmp_path: Path,
):
    project_path = tmp_path / "album.photoalbum"

    first = ProjectService()
    first.create(project_path)

    expected = create_album_settings()

    first.set_album_structure_settings(
        expected
    )
    first.close()

    reopened = ProjectService()
    reopened.open(project_path)

    actual = reopened.get_album_structure_settings()

    assert actual == expected

    reopened.close()


def test_missing_album_settings_return_none(
    tmp_path: Path,
):
    project_path = tmp_path / "album.photoalbum"

    service = ProjectService()
    service.create(project_path)

    assert (
        service.get_album_structure_settings()
        is None
    )

    service.close()

@pytest.mark.parametrize('operation', ['find', 'resolve'])
def test_photo_access_requires_open_project(operation):
    service = ProjectService()
    with pytest.raises(RuntimeError, match='No project is currently open'):
        if operation == 'find':
            service.find_photo(Path('photo.jpg'))
        else:
            service.resolve_location(48.0, 2.0, user_agent='PhotoAlbum/test')


def test_find_photo_missing_from_project(tmp_path):
    service = ProjectService()
    service.create(tmp_path / 'album.photoalbum')
    try:
        assert service.find_photo(tmp_path / 'missing.jpg') is None
    finally:
        service.close()


def test_remote_source_selection_is_persisted_without_credentials(tmp_path):
    project_path = tmp_path / "album.photoalbum"
    source = ProjectSource(
        id="synology-1",
        kind="synology-photos",
        name="Family NAS",
        collection_id="7",
        collection_name="Summer",
        config={
            "base_url": "https://nas.example:5001",
            "username": "alice",
            "verify_tls": True,
        },
    )
    service = ProjectService()
    service.create(project_path)
    service.change_photo_source(source, _RemoteProvider())
    service.close()

    reopened = ProjectService()
    reopened.open(project_path)
    try:
        assert reopened.get_photo_source() == source
        assert "password" not in project_path.read_bytes().decode(
            "utf-8", errors="ignore"
        )
    finally:
        reopened.close()


class _RemoteProvider:
    kind = "fake"

    def __init__(self, assets=(), *, fail=False):
        self.assets = list(assets)
        self.fail = fail
        self.list_calls = 0
        self.original_fetches = 0
        self.closed = False

    def list_assets(self, collection_id):
        self.list_calls += 1
        if self.fail:
            raise RuntimeError("snapshot failed")
        return list(self.assets)

    def fetch_thumbnail(self, asset, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"thumbnail")
        return destination

    def fetch_original(self, asset, destination):
        self.original_fetches += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"original")
        return destination

    def close(self):
        self.closed = True


def _remote_source(source_id, collection_id):
    return ProjectSource(
        id=source_id, kind="fake", name=source_id,
        collection_id=collection_id, collection_name=collection_id,
    )


def test_failed_source_change_keeps_previous_source_and_snapshot(tmp_path):
    service = ProjectService()
    service.create(tmp_path / "album.photoalbum")
    old_source = _remote_source("old-source", "old-album")
    old_provider = _RemoteProvider([
        SourceAsset(id="old-photo", filename="old.jpg")
    ])
    service.change_photo_source(old_source, old_provider)

    candidate = _remote_source("new-source", "new-album")
    failing_provider = _RemoteProvider(fail=True)
    with pytest.raises(RuntimeError, match="snapshot failed"):
        service.change_photo_source(candidate, failing_provider)

    assert service.get_photo_source() == old_source
    assert [photo.identity for photo in service.list_photos()] == [
        "old-source:old-photo"
    ]
    assert failing_provider.closed is True
    assert old_provider.closed is False
    service.close()


def test_remote_source_configuration_can_be_saved_without_import(tmp_path):
    service = ProjectService()
    service.create(tmp_path / "album.photoalbum")
    source = _remote_source("remote", "album")
    service.set_photo_source(source)
    assert service.get_photo_source() == source
    assert service.list_photos() == []
    service.close()


def test_reconnect_does_not_resynchronize_snapshot(tmp_path):
    project_path = tmp_path / "album.photoalbum"
    source = _remote_source("remote-source", "album")
    initial = _RemoteProvider([
        SourceAsset(id="photo", filename="photo.jpg", revision="one")
    ])
    service = ProjectService()
    service.create(project_path)
    service.change_photo_source(source, initial)
    service.close()

    reopened = ProjectService()
    reopened.open(project_path)
    provider = _RemoteProvider([
        SourceAsset(id="unexpected", filename="unexpected.jpg")
    ])
    reopened.attach_source_session(source.id, provider)
    photo = reopened.list_photos()[0]
    reopened.materialize_originals([photo])

    assert provider.list_calls == 0
    assert provider.original_fetches == 1
    assert [item.identity for item in reopened.list_photos()] == [
        "remote-source:photo"
    ]

    reopened.sync_photo_source()
    assert provider.list_calls == 1
    assert [item.identity for item in reopened.list_photos()] == [
        "remote-source:unexpected"
    ]
    reopened.close()


def test_photo_metadata_policy_defaults_for_local_source(tmp_path: Path):
    from photoalbum.sources import PhotoMetadataPolicy

    project_path = tmp_path / "local-policy.photoalbum"

    service = ProjectService()
    service.create(project_path)
    service.set_source_directory(tmp_path / "photos")

    policy = service.get_photo_metadata_policy()

    assert policy == PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference="geocoding",
        nominatim_enabled=True,
    )

    service.close()


def test_photo_metadata_policy_defaults_for_remote_source(tmp_path: Path):
    from photoalbum.sources import PhotoMetadataPolicy

    project_path = tmp_path / "remote-policy.photoalbum"

    service = ProjectService()
    service.create(project_path)

    source = _remote_source("remote-1", "album")
    provider = _RemoteProvider()
    service.change_photo_source(source, provider)

    policy = service.get_photo_metadata_policy()

    assert policy == PhotoMetadataPolicy(
        date_preference="source",
        gps_preference="source",
        location_preference="source",
        nominatim_enabled=False,
    )

    service.close()


def test_photo_metadata_policy_is_persisted(tmp_path: Path):
    from photoalbum.sources import PhotoMetadataPolicy

    project_path = tmp_path / "persisted-policy.photoalbum"

    service = ProjectService()
    service.create(project_path)
    service.set_photo_source(ProjectSource(id="local", kind="local", name="Local",
        collection_id="photos", collection_name="Photos", config={"directory": str(tmp_path / "photos")}))

    policy = PhotoMetadataPolicy(
        date_preference="source",
        gps_preference="exif",
        location_preference="none",
        nominatim_enabled=False,
    )
    service.set_photo_metadata_policy(policy)
    service.close()

    reopened = ProjectService()
    reopened.open(project_path)

    assert reopened.get_photo_metadata_policy() == policy

    reopened.close()


def test_photo_metadata_policy_does_not_trigger_processing(tmp_path: Path):
    from photoalbum.sources import PhotoMetadataPolicy

    project_path = tmp_path / "policy-no-processing.photoalbum"

    service = ProjectService()
    service.create(project_path)
    service.set_photo_source(ProjectSource(id="local", kind="local", name="Local",
        collection_id="photos", collection_name="Photos", config={"directory": str(tmp_path / "photos")}))

    policy = PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference="geocoding",
        nominatim_enabled=True,
    )

    service.set_photo_metadata_policy(policy)

    assert service.get_photo_metadata_policy() == policy

    service.close()


def test_photo_metadata_policy_rejects_invalid_values():
    import pytest

    from photoalbum.sources import PhotoMetadataPolicy

    with pytest.raises(ValueError, match="date preference"):
        PhotoMetadataPolicy(
            date_preference="invalid",
            gps_preference="exif",
            location_preference="geocoding",
            nominatim_enabled=True,
        )

    with pytest.raises(ValueError, match="GPS preference"):
        PhotoMetadataPolicy(
            date_preference="exif",
            gps_preference="invalid",
            location_preference="geocoding",
            nominatim_enabled=True,
        )

    with pytest.raises(ValueError, match="location preference"):
        PhotoMetadataPolicy(
            date_preference="exif",
            gps_preference="exif",
            location_preference="invalid",
            nominatim_enabled=True,
        )


def test_apply_photo_metadata_policy_recomputes_effective_values(tmp_path: Path):
    from datetime import datetime

    from photoalbum.database import PhotoRepository
    from photoalbum.models import DateSource, GpsSource, Photo
    from photoalbum.sources import PhotoMetadataPolicy

    project_path = tmp_path / "apply-policy.photoalbum"

    service = ProjectService()
    service.create(project_path)
    service.set_photo_source(ProjectSource(id="local", kind="local", name="Local",
        collection_id="photos", collection_name="Photos", config={"directory": str(tmp_path / "photos")}))

    repository = PhotoRepository(service._require_database())
    path = (tmp_path / "photo.jpg").resolve()

    repository.save(
        Photo(
            path=path,
            filename=path.name,
            capture_datetime=datetime(2020, 1, 1),
            date_source=DateSource.EXIF,
            latitude=47.0,
            longitude=-1.0,
            gps_source=GpsSource.EXIF,
            exif_capture_datetime=datetime(2020, 1, 1),
            source_capture_datetime=datetime(2024, 7, 1),
            exif_latitude=47.0,
            exif_longitude=-1.0,
            source_latitude=48.0,
            source_longitude=2.0,
            source_location_data={
                "provider": "synology",
                "city": "Paris",
                "address": "Paris, France",
            },
        )
    )

    policy = PhotoMetadataPolicy(
        date_preference="source",
        gps_preference="source",
        location_preference="source",
        nominatim_enabled=False,
    )

    service.apply_photo_metadata_policy(policy)

    loaded = service.find_photo(path)
    assert loaded is not None
    assert loaded.capture_datetime == datetime(2024, 7, 1)
    assert loaded.date_source == DateSource.SOURCE
    assert (loaded.latitude, loaded.longitude) == (48.0, 2.0)
    assert loaded.gps_source == GpsSource.SOURCE
    assert loaded.city == "Paris"

    service.close()
