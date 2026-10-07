from unittest.mock import Mock

import pytest

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.geocoding import GeocodingError
from photoalbum.gui.workers.sources_refresh_worker import SourcesRefreshWorker
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.scanner import LibraryScanResult
from photoalbum.sources import PhotoMetadataPolicy, ProjectSource


@pytest.mark.parametrize("language", ["fr", "en"])
@pytest.mark.parametrize("synchronize", [False, True])
def test_cancelled_local_scan_logs_stop_not_success(tmp_path, monkeypatch, language, synchronize):
    project_path = tmp_path / "cancelled.photoalbum"
    database = ProjectDatabase(project_path)
    database.initialize()
    database.close()
    sources = [
        ProjectSource(
            id=name, kind="local", name=name, collection_id=name,
            collection_name=name, config={"directory": str(tmp_path)},
        )
        for name in ("First", "Second")
    ]
    scan = Mock(return_value=LibraryScanResult(cancelled=True))
    monkeypatch.setattr(
        "photoalbum.gui.workers.sources_refresh_worker.ProjectScanService.scan", scan
    )
    worker = SourcesRefreshWorker(
        project_path=project_path, sources=sources, providers={},
        synchronize=synchronize, language=language, user_agent="tests",
    )
    logs, completed = [], []
    worker.log_message.connect(logs.append)
    worker.completed.connect(completed.append)

    worker.run()

    translator = Translator(language)
    name = f"{translator.tr('sources.local_folder')} — First"
    prefix = "sources.sync" if synchronize else "sources.refresh_one"
    assert logs[-1] == translator.tr("sources.processing_cancelled", source=name)
    assert translator.tr(f"{prefix}.completed", source=name) not in logs
    scan.assert_called_once()
    assert len(completed) == 1  # Keep the project reload after partial work.


@pytest.mark.parametrize("language", ["fr", "en"])
@pytest.mark.parametrize("synchronize", [False, True])
def test_remote_geocoding_error_logs_partial_result_not_success(
    tmp_path, monkeypatch, language, synchronize,
):
    project_path = tmp_path / "remote.photoalbum"
    source = ProjectSource(
        id="remote", kind="synology-photos", name="Remote", collection_id="album",
        collection_name="Album", provider_label="Synology Photos",
        metadata_policy=PhotoMetadataPolicy("source", "source", "none", True),
    )
    photo = Photo(
        path=tmp_path / "photo.jpg", filename="photo.jpg", source_id=source.id,
        source_latitude=48.0, source_longitude=2.0,
    )
    database = ProjectDatabase(project_path)
    database.initialize()
    PhotoRepository(database).save(photo)
    database.close()
    # Only provider import is simulated; metadata/geocoding uses the real worker.
    monkeypatch.setattr(
        "photoalbum.gui.workers.sources_refresh_worker.SourceImporter.import_collection",
        Mock(return_value=Mock(photos=[photo], added=0, updated=1, missing=0)),
    )
    resolver = Mock()
    resolver.resolve_with_source.side_effect = GeocodingError("offline")
    monkeypatch.setattr(
        "photoalbum.gui.workers.metadata_refresh_worker.create_nominatim_location_resolver",
        lambda *args, **kwargs: resolver,
    )
    worker = SourcesRefreshWorker(
        project_path=project_path, sources=[source], providers={source.id: Mock()},
        synchronize=synchronize, language=language, user_agent="tests",
    )
    logs, completed = [], []
    worker.log_message.connect(logs.append)
    worker.completed.connect(completed.append)

    worker.run()

    translator = Translator(language)
    name = "Synology Photos — Album"
    prefix = "sources.sync" if synchronize else "sources.refresh_one"
    resolver.resolve_with_source.assert_called_once()
    assert logs[-1] == "⚠ " + translator.tr("sources.geocoding_incomplete", source=name)
    assert translator.tr(f"{prefix}.completed", source=name) not in logs
    assert len(completed) == 1
    assert [item.identity for item in completed[0]] == [photo.identity]
