from datetime import datetime
from pathlib import Path

from PIL import Image

from photoalbum.app import ProjectScanService
from photoalbum.database import ProjectDatabase


def create_image(path: Path) -> None:
    image = Image.new("RGB", (800, 600))
    image.save(path)


def test_project_scan_service_scans_and_persists_photos(
    tmp_path: Path,
):
    project_path = tmp_path / "album.photoalbum"
    source_directory = tmp_path / "photos"
    source_directory.mkdir()

    create_image(
        source_directory / "2025-01-01.jpg"
    )

    database = ProjectDatabase(project_path)
    database.initialize()
    database.close()

    service = ProjectScanService()

    result = service.scan(
        project_path=project_path,
        source_directory=source_directory,
    )

    assert result.statistics.discovered == 1
    assert result.statistics.analyzed == 1
    assert len(result.photos) == 1

    second_result = service.scan(
        project_path=project_path,
        source_directory=source_directory,
    )

    assert second_result.statistics.analyzed == 0
    assert second_result.statistics.reused == 1


def test_scan_applies_metadata_policy_without_geocoding(tmp_path: Path):
    from photoalbum.database import PhotoRepository
    from photoalbum.models import DateSource
    from photoalbum.sources import PhotoMetadataPolicy

    project_path = tmp_path / "album.photoalbum"
    source_directory = tmp_path / "photos"
    source_directory.mkdir()

    image_path = source_directory / "2025-01-01.jpg"
    create_image(image_path)

    database = ProjectDatabase(project_path)
    database.initialize()
    database.close()

    policy = PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference="none",
        nominatim_enabled=False,
    )

    service = ProjectScanService()
    result = service.scan(
        project_path=project_path,
        source_directory=source_directory,
        metadata_policy=policy,
    )

    assert len(result.photos) == 1
    assert result.photos[0].capture_datetime == (
        datetime(2025, 1, 1)
    )
    assert result.photos[0].date_source == DateSource.FILENAME

    database = ProjectDatabase(project_path)
    database.initialize()
    try:
        repository = PhotoRepository(database)
        persisted = repository.find_by_path(image_path)
        assert persisted is not None
        assert persisted.capture_datetime == (
            datetime(2025, 1, 1)
        )
        assert persisted.date_source == DateSource.FILENAME
    finally:
        database.close()


def test_scan_requires_user_agent_only_when_policy_enables_nominatim(
    tmp_path: Path,
):
    from photoalbum.sources import PhotoMetadataPolicy

    project_path = tmp_path / "album.photoalbum"
    source_directory = tmp_path / "photos"
    source_directory.mkdir()

    database = ProjectDatabase(project_path)
    database.initialize()
    database.close()

    policy = PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference="geocoding",
        nominatim_enabled=True,
    )

    service = ProjectScanService()

    try:
        service.scan(
            project_path=project_path,
            source_directory=source_directory,
            metadata_policy=policy,
            user_agent=None,
        )
    except ValueError as exc:
        assert "User-Agent" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_scan_reports_metadata_and_nominatim_phases_without_network(
    tmp_path: Path,
):
    from photoalbum.scanner import ScanProgressPhase
    from photoalbum.sources import PhotoMetadataPolicy

    project_path = tmp_path / "album.photoalbum"
    source_directory = tmp_path / "photos"
    source_directory.mkdir()

    create_image(source_directory / "2025-01-01.jpg")
    create_image(source_directory / "2025-02-01.jpg")

    database = ProjectDatabase(project_path)
    database.initialize()
    database.close()

    progress = []

    policy = PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference="none",
        nominatim_enabled=False,
    )

    result = ProjectScanService().scan(
        project_path=project_path,
        source_directory=source_directory,
        metadata_policy=policy,
        on_phase_progress=progress.append,
    )

    assert result.cancelled is False

    metadata = [
        item
        for item in progress
        if item.phase == ScanProgressPhase.METADATA
    ]
    nominatim = [
        item
        for item in progress
        if item.phase == ScanProgressPhase.NOMINATIM
    ]

    assert metadata
    assert metadata[-1].current == 2
    assert metadata[-1].total == 2
    assert nominatim == []
