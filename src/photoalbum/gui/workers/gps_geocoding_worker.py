from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from photoalbum.database import ProjectDatabase
from photoalbum.geocoding import (
    create_nominatim_location_resolver,
)


class GpsGeocodingWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        project_path: Path,
        latitude: float,
        longitude: float,
        language: str | None = None,
        user_agent: str,
    ) -> None:
        super().__init__()

        self._project_path = project_path
        self._latitude = latitude
        self._longitude = longitude
        self._language = language
        self._user_agent = user_agent

    @Slot()
    def run(self) -> None:
        database = ProjectDatabase(
            self._project_path
        )

        try:
            database.initialize()

            resolver = (
                create_nominatim_location_resolver(
                    database,
                    user_agent=self._user_agent,
                )
            )

            location = resolver.resolve(
                self._latitude,
                self._longitude,
                language=self._language,
            )

        except Exception as exc:
            self.failed.emit(str(exc))
            return

        finally:
            database.close()

        self.completed.emit(location)
