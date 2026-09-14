from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from photoalbum.app import ProjectScanService
from photoalbum.scanner import ProcessingEvent


class ScanWorker(QObject):
    event_received = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        project_path: Path,
        source_directory: Path,
        recursive: bool,
        language: str | None = None,
        geocode: bool = False,
        user_agent: str | None = None,
    ) -> None:
        super().__init__()

        self._project_path = project_path
        self._source_directory = source_directory
        self._recursive = recursive
        self._language = language
        self._geocode = geocode
        self._user_agent = user_agent

    @Slot()
    def run(self) -> None:
        service = ProjectScanService()

        try:
            result = service.scan(
                project_path=self._project_path,
                source_directory=self._source_directory,
                recursive=self._recursive,
                language=self._language,
                geocode=self._geocode,
                user_agent=self._user_agent,
                on_event=self._handle_event,
            )

        except Exception as exc:
            self.failed.emit(str(exc))
            return

        self.completed.emit(result)

    def _handle_event(
        self,
        event: ProcessingEvent,
    ) -> None:
        self.event_received.emit(event)