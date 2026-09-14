from pathlib import Path

import pytest

from photoalbum.app import ProjectService


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

