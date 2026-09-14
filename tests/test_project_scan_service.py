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
