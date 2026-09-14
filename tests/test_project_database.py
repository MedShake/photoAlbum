from pathlib import Path

from photoalbum.database import ProjectDatabase


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
        database.get_schema_version()
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

import sqlite3

import pytest


def test_initialize_is_idempotent(tmp_path: Path):
    project_path = tmp_path / "family-2025.photoalbum"

    database = ProjectDatabase(project_path)

    database.initialize()
    database.initialize()

    assert (
        database.get_schema_version()
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

