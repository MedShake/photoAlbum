from __future__ import annotations

from datetime import datetime
from pathlib import Path

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.models import Photo

from photoalbum.album import (
    AlbumStructureSettings,
    album_settings_from_json,
    album_settings_to_json,
)

class ProjectService:
    SOURCE_DIRECTORY_KEY = "source_directory"
    RECURSIVE_SCAN_KEY = "recursive_scan"
    ALBUM_STRUCTURE_SETTINGS_KEY = "album_structure_settings"

    def __init__(self) -> None:
        self._database: ProjectDatabase | None = None

    @property
    def is_open(self) -> bool:
        return self._database is not None

    @property
    def project_path(self) -> Path | None:
        if self._database is None:
            return None

        return self._database.path

    def create(self, path: Path) -> None:
        self.close()

        path = path.expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        self._database = ProjectDatabase(path)
        self._database.initialize()

    def open(self, path: Path) -> None:
        self.close()

        path = path.expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"Project does not exist: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Project path is not a file: {path}"
            )

        self._database = ProjectDatabase(path)
        self._database.initialize()

    def list_photos(self) -> list[Photo]:
        database = self._require_database()

        repository = PhotoRepository(database)

        return repository.list_all()

    def set_manual_capture_datetime(
        self,
        photo_path: Path,
        capture_datetime: datetime,
    ) -> None:
        database = self._require_database()

        repository = PhotoRepository(database)

        repository.set_manual_capture_datetime(
            photo_path,
            capture_datetime,
        )

    def close(self) -> None:
        if self._database is not None:
            self._database.close()
            self._database = None

    def set_source_directory(
        self,
        directory: Path,
    ) -> None:
        database = self._require_database()

        directory = directory.expanduser().resolve()

        database.set_project_metadata(
            self.SOURCE_DIRECTORY_KEY,
            str(directory),
        )

    def get_source_directory(self) -> Path | None:
        database = self._require_database()

        value = database.get_project_metadata(
            self.SOURCE_DIRECTORY_KEY
        )

        if value is None:
            return None

        return Path(value)

    def set_recursive_scan(
        self,
        recursive: bool,
    ) -> None:
        database = self._require_database()

        database.set_project_metadata(
            self.RECURSIVE_SCAN_KEY,
            "1" if recursive else "0",
        )

    def get_recursive_scan(self) -> bool:
        database = self._require_database()

        value = database.get_project_metadata(
            self.RECURSIVE_SCAN_KEY
        )

        return value == "1"


    def set_album_structure_settings(
        self,
        settings: AlbumStructureSettings,
    ) -> None:
        database = self._require_database()

        database.set_project_metadata(
            self.ALBUM_STRUCTURE_SETTINGS_KEY,
            album_settings_to_json(settings),
        )

    def get_album_structure_settings(
        self,
    ) -> AlbumStructureSettings | None:
        database = self._require_database()

        value = database.get_project_metadata(
            self.ALBUM_STRUCTURE_SETTINGS_KEY
        )

        if value is None:
            return None

        return album_settings_from_json(value)

    def _require_database(self) -> ProjectDatabase:
        if self._database is None:
            raise RuntimeError("No project is currently open.")

        return self._database

