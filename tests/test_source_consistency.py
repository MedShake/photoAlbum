from dataclasses import replace
from io import BytesIO
import json
from unittest.mock import Mock
from urllib.error import URLError

import pytest
from PIL import ExifTags, Image
from PIL.TiffImagePlugin import IFDRational
from PySide6.QtWidgets import QApplication

from photoalbum.app import ProjectScanService, ProjectService
from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.geocoding import GeocodingError
from photoalbum.gui.scan_controller import ScanController
from photoalbum.gui.widgets.photo_sources_widget import PhotoSourcesWidget
from photoalbum.gui.workers.sources_refresh_worker import SourcesRefreshWorker
from photoalbum.gui.workers.source_sync_worker import SourceSyncWorker
from photoalbum.i18n import Translator
from photoalbum.metadata import ExifReader
from photoalbum.models import Photo, GpsCandidate, MetadataCandidates, GpsSource, Location
from photoalbum.sources import (
    PhotoMetadataPolicy, ProjectSource, SourceAsset, SourceAssetCache,
    SynologyPhotosSource, SynologyCredentials, SourceReconnectRequiredError,
    resolve_photo_metadata,
)
from photoalbum.sources.base import AuthenticationError, SourceError
from photoalbum.sources.operation import SourceOperationResult


@pytest.mark.parametrize("latitude,longitude", [
    (float("nan"), 2), (48, float("inf")), (-float("inf"), 2),
    (91, 2), (48, -181), (None, 2), ("48", 2), (True, 2), (10**400, 2),
])
def test_invalid_gps_is_absent_and_policy_uses_valid_fallback(latitude, longitude):
    photo = Photo(
        path=None, filename="photo.jpg", asset_id="1",
        latitude=latitude, longitude=longitude,
        metadata_candidates=MetadataCandidates(gps={
            "exif": GpsCandidate(latitude, longitude),
            "provider": GpsCandidate(48, 2),
        }),
    )
    assert not photo.has_gps
    resolved = resolve_photo_metadata(photo, PhotoMetadataPolicy.for_source_kind("local"))
    assert resolved.has_gps and resolved.gps_source == GpsSource.SOURCE
    assert (resolved.latitude, resolved.longitude) == (48, 2)
    photo.metadata_candidates.gps.pop("provider")
    resolved = resolve_photo_metadata(photo, PhotoMetadataPolicy.for_source_kind("local"))
    assert (resolved.latitude, resolved.longitude) == (None, None)


@pytest.mark.parametrize("degrees", [(0, 0), (1, 0), (91, 1)])
def test_invalid_exif_gps_does_not_fail_source_scan(tmp_path, monkeypatch, degrees):
    folder = tmp_path / "photos"
    folder.mkdir()
    exif = Image.Exif()
    exif[ExifTags.IFD.GPSInfo] = {
        1: "N", 2: (IFDRational(*degrees), IFDRational(0), IFDRational(0)),
        3: "E", 4: (IFDRational(2), IFDRational(0), IFDRational(0)),
    }
    path = folder / "2025-01-01.jpg"
    Image.new("RGB", (10, 10)).save(path, exif=exif)
    assert ExifReader().read(path).latitude is None
    resolver = Mock()
    monkeypatch.setattr("photoalbum.app.project_scan_service.create_nominatim_location_resolver", lambda *a, **kw: resolver)
    result = ProjectScanService().scan(
        project_path=tmp_path / "gps.photoalbum", source_directory=folder,
        metadata_policy=PhotoMetadataPolicy("exif", "exif", "geocoding", True),
        user_agent="tests",
    )
    assert not result.errors and len(result.photos) == 1
    assert not result.photos[0].has_gps
    resolver.resolve_with_source.assert_not_called()


def test_new_local_source_never_geocodes_implicitly_and_persists(tmp_path, monkeypatch):
    service = ProjectService()
    path = tmp_path / "local.photoalbum"
    service.create(path)
    folder = tmp_path / "photos"
    folder.mkdir()
    Image.new("RGB", (10, 10)).save(folder / "2025-01-01.jpg")
    source = service.add_local_source(folder)
    factory = Mock(side_effect=AssertionError("Unexpected network geocoding"))
    monkeypatch.setattr("photoalbum.app.project_scan_service.create_nominatim_location_resolver", factory)
    result = ProjectScanService().scan(
        project_path=path, source_directory=folder, source_id=source.id,
        metadata_policy=source.effective_metadata_policy,
    )
    assert not result.errors
    factory.assert_not_called()
    service.close()
    service.open(path)
    assert service.get_photo_metadata_policy(source.id) == PhotoMetadataPolicy("exif", "exif", "none", False)
    service.close()


def run_worker(service, source, **kwargs):
    worker = SourcesRefreshWorker(
        project_path=service.project_path, sources=[source], providers={},
        synchronize=False, language="en", user_agent="tests", **kwargs,
    )
    outcomes, photos, logs = [], [], []
    worker.source_result.connect(outcomes.append)
    worker.completed.connect(photos.append)
    worker.log_message.connect(logs.append)
    worker.run()
    return outcomes, photos, logs


@pytest.mark.parametrize("failure", ["missing", "permission"])
def test_unavailable_local_source_preserves_snapshot_and_reports_access(tmp_path, monkeypatch, failure):
    service = ProjectService()
    service.create(tmp_path / "local.photoalbum")
    folder = tmp_path / "photos"
    folder.mkdir()
    image = folder / "2025-01-01.jpg"
    Image.new("RGB", (10, 10)).save(image)
    source = service.add_local_source(folder)
    run_worker(service, source)
    if failure == "missing":
        folder.rename(tmp_path / "moved")
    else:
        original = __import__("os").scandir

        def scandir(path):
            if str(path) == str(folder):
                raise PermissionError("denied")
            return original(path)

        monkeypatch.setattr("os.scandir", scandir)
    outcomes, photos, logs = run_worker(service, source)
    assert outcomes[0].status == "failed" and outcomes[0].issue == "access"
    assert len(photos[0]) == len(service.list_photos()) == 1
    assert service.source_status(source) == "unavailable"
    assert "failed" in logs[-1]
    service.close()


@pytest.mark.parametrize("failure", ["file", "geocoding"])
def test_local_partial_results_do_not_announce_success(tmp_path, monkeypatch, failure):
    service = ProjectService()
    service.create(tmp_path / "partial.photoalbum")
    folder = tmp_path / "photos"
    folder.mkdir()
    image = folder / "2025-01-01.jpg"
    Image.new("RGB", (10, 10)).save(image)
    source = service.add_local_source(folder)
    if failure == "file":
        (folder / "bad.jpg").write_bytes(b"broken image")
    else:
        source = replace(source, metadata_policy=PhotoMetadataPolicy("exif", "exif", "geocoding", True))
        original = ExifReader.read

        def read(reader, path):
            return replace(original(reader, path), latitude=48, longitude=2)

        monkeypatch.setattr(ExifReader, "read", read)
        resolver = Mock()
        resolver.resolve_with_source.side_effect = GeocodingError("offline")
        monkeypatch.setattr("photoalbum.app.project_scan_service.create_nominatim_location_resolver", lambda *a, **kw: resolver)
    outcomes, photos, logs = run_worker(service, source)
    assert outcomes[0].status == "partial"
    assert outcomes[0].issue == ("metadata" if failure == "file" else "geocoding")
    assert len(photos[0]) == 1
    assert "completed for" not in logs[-1]
    service.close()


@pytest.mark.parametrize("status,issue", [("success", None), ("failed", "access"), ("partial", "geocoding"), ("cancelled", None)])
def test_controller_preserves_real_outcome_in_service_and_ui(tmp_path, status, issue):
    app = QApplication.instance() or QApplication([])
    service = ProjectService()
    service.create(tmp_path / "outcome.photoalbum")
    source = service.add_local_source(tmp_path)
    view = PhotoSourcesWidget(Translator("en"))
    controller = ScanController(service, view, Translator("en"), language="en")
    controller._operation_kind = "sources"
    controller._source_result_received(SourceOperationResult(source.id, status, issue))
    controller._metadata_refresh_completed([])
    assert controller.analysis_completed == (status == "success")
    assert (service.source_status(source) is None) == (status == "success")
    if status != "success":
        assert view.summary_label.text() != Translator("en").tr("main.analysis_completed")
    view.close()
    service.close()


@pytest.mark.parametrize("code,invalid", [(106, True), (107, True), (119, True), (105, False)])
@pytest.mark.parametrize("download", [False, True])
def test_synology_session_errors_are_distinct_from_permissions(tmp_path, code, invalid, download):
    opener = Mock()
    response = BytesIO(json.dumps({"success": False, "error": {"code": code}}).encode())
    response.headers = {"Content-Type": "application/json"}
    opener.open.return_value = response
    provider = SynologyPhotosSource("https://nas.example", SynologyCredentials("user", "pw"), opener=opener)
    provider._connected = True
    with pytest.raises(AuthenticationError if invalid else SourceError):
        if download:
            provider.fetch_original(SourceAsset(id="1", filename="photo.jpg"), tmp_path / "original.jpg")
        else:
            provider.list_assets("album")
    assert provider.session_invalid is invalid
    assert not (tmp_path / "original.jpg").exists()


def test_synology_network_error_keeps_session(tmp_path):
    opener = Mock()
    opener.open.side_effect = URLError("offline")
    provider = SynologyPhotosSource("https://nas.example", SynologyCredentials("user", "pw"), opener=opener)
    provider._connected = True
    with pytest.raises(SourceError) as error:
        provider.list_assets("album")
    assert not isinstance(error.value, AuthenticationError)
    assert not provider.session_invalid


def test_original_auth_failure_requires_reconnection_but_cache_still_works(tmp_path):
    service = ProjectService()
    service.create(tmp_path / "remote.photoalbum")
    source = ProjectSource(id="remote", kind="synology-photos", name="Remote", collection_id="album", collection_name="Album")
    opener = Mock()
    response = BytesIO(b'{"success":false,"error":{"code":119}}')
    response.headers = {"Content-Type": "application/json"}
    opener.open.return_value = response
    provider = SynologyPhotosSource("https://nas.example", SynologyCredentials("user", "pw"), opener=opener)
    provider._connected = True
    service.set_photo_source(source, provider)
    photo = Photo(path=None, filename="photo.jpg", source_id=source.id, asset_id="1")
    with pytest.raises(SourceReconnectRequiredError):
        service.materialize_originals([photo])
    assert service.get_photo_source_session(source.id) is None
    assert service.source_status(source) == "invalid_session"
    cache = SourceAssetCache(service.project_path)
    path = cache.path_for(photo, "original")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"cached")
    service.materialize_originals([photo])
    assert photo.path == path
    service.close()


def test_changed_remote_album_runs_geocoding_and_keeps_atomic_snapshot(tmp_path, monkeypatch):
    from tests.test_photo_sources import FakeRemoteSource
    from photoalbum.geocoding.location_resolver import LocationResolution, LocationResolutionSource

    service = ProjectService()
    service.create(tmp_path / "changed.photoalbum")
    source = ProjectSource(
        id="remote", kind="fake", name="Old", collection_id="old", collection_name="Old",
        metadata_policy=PhotoMetadataPolicy("source", "source", "geocoding", True),
    )
    service.set_photo_source(source)
    database = ProjectDatabase(service.project_path)
    PhotoRepository(database).save(Photo(path=None, filename="old.jpg", source_id=source.id, asset_id="old"))
    database.close()
    changed = replace(source, collection_id="album", collection_name="New")
    provider = FakeRemoteSource([SourceAsset(id="new", filename="new.jpg", latitude=48, longitude=2)])
    resolver = Mock()
    resolver.resolve_with_source.return_value = LocationResolution(
        location=Location(latitude=48, longitude=2, city="Paris"), source=LocationResolutionSource.REVERSE,
    )
    monkeypatch.setattr("photoalbum.gui.workers.metadata_refresh_worker.create_nominatim_location_resolver", lambda *a, **kw: resolver)
    worker = SourceSyncWorker(
        project_path=service.project_path, source=changed, provider=provider,
        publish_source=True, language="en", user_agent="tests",
    )
    completed, outcomes = [], []
    worker.completed.connect(completed.append)
    worker.source_result.connect(outcomes.append)
    worker.run()
    assert outcomes[0].status == "success"
    assert completed[0].photos[0].city == "Paris"
    assert completed[0].missing == 1
    assert service.get_photo_source(source.id).collection_id == "album"
    assert [photo.asset_id for photo in service.list_photos()] == ["new"]
    resolver.resolve_with_source.assert_called_once()
    service.close()


@pytest.mark.parametrize("error,expected", [(AuthenticationError("expired"), "invalid_session"), (SourceError("offline"), "unavailable")])
def test_worker_access_failure_updates_card_state_without_losing_snapshot(tmp_path, error, expected):
    service = ProjectService()
    service.create(tmp_path / "failure.photoalbum")
    source = ProjectSource(id="remote", kind="synology-photos", name="Remote", collection_id="album", collection_name="Album")
    provider = Mock()
    provider.list_assets.side_effect = error
    service.set_photo_source(source, provider)
    database = ProjectDatabase(service.project_path)
    PhotoRepository(database).save(Photo(path=None, filename="stored.jpg", source_id=source.id, asset_id="1"))
    database.close()
    worker = SourcesRefreshWorker(
        project_path=service.project_path, sources=[source], providers={source.id: provider},
        synchronize=True, language="en", user_agent="tests",
    )
    worker.source_result.connect(service.record_source_result)
    worker.run()
    assert service.source_status(source) == expected
    assert len(service.list_photos()) == 1
    assert (service.get_photo_source_session(source.id) is None) == isinstance(error, AuthenticationError)
    service.close()


def test_open_original_without_session_has_actionable_message(tmp_path):
    from photoalbum.gui.photo_editor import PhotoEditor

    app = QApplication.instance() or QApplication([])
    service = ProjectService()
    service.create(tmp_path / "open.photoalbum")
    source = ProjectSource(id="remote", kind="synology-photos", name="Remote", collection_id="album", collection_name="Album")
    service.set_photo_source(source)
    photo = Photo(path=None, filename="absent.jpg", source_id=source.id, asset_id="1")
    editor = PhotoEditor(service, Translator("en"), language="en")
    errors = []
    editor.error.connect(errors.append)
    editor.open_in_os(photo)
    assert errors == [Translator("en").tr("source.asset.reconnect_required", filename=photo.filename)]
    service.close()


def test_failed_album_edit_does_not_invalidate_previous_session(tmp_path):
    app = QApplication.instance() or QApplication([])
    service = ProjectService()
    service.create(tmp_path / "edit.photoalbum")
    source = ProjectSource(id="remote", kind="synology-photos", name="Remote", collection_id="old", collection_name="Old")
    provider = Mock()
    service.set_photo_source(source, provider)
    view = PhotoSourcesWidget(Translator("en"))
    controller = ScanController(service, view, Translator("en"), language="en")
    controller._operation_kind = "source_import"
    controller._source_result_received(SourceOperationResult(source.id, "failed", "authentication", "expired candidate"))
    assert service.get_photo_source_session(source.id) is provider
    assert service.get_photo_source(source.id).collection_id == "old"
    assert service.source_status(source) == "failed"
    view.close()
    service.close()
