from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.geocoding import create_nominatim_location_resolver
from photoalbum.scanner import (
    LibraryScanner,
    PhotoProcessor,
    ScanProgress,
    ScanProgressPhase,
)
from photoalbum.sources import PhotoMetadataPolicy, resolve_photo_metadata


class MetadataRefreshWorker(QObject):
    """Resolve a persisted snapshot without contacting its photo provider."""

    phase_progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        project_path: Path,
        policy: PhotoMetadataPolicy,
        source_id: str | None = None,
        language: str | None,
        user_agent: str,
    ) -> None:
        super().__init__()
        self._project_path = project_path
        self._policy = policy
        self._source_id = source_id
        self._language = language
        self._user_agent = user_agent
        self._cancel_requested = False

    @Slot()
    def run(self) -> None:
        database = ProjectDatabase(self._project_path)
        try:
            database.initialize()
            repository = PhotoRepository(database)
            photos = (repository.list_by_source(self._source_id) if self._source_id else repository.list_all())
            total = len(photos)
            self.phase_progress.emit(
                ScanProgress(ScanProgressPhase.METADATA, 0, total)
            )
            with repository.atomic():
                for index, photo in enumerate(photos, start=1):
                    if self._cancel_requested:
                        break
                    repository.save(
                        resolve_photo_metadata(photo, self._policy),
                        commit=False,
                    )
                    self.phase_progress.emit(
                        ScanProgress(ScanProgressPhase.METADATA, index, total)
                    )

            photos = (repository.list_by_source(self._source_id) if self._source_id else repository.list_all())
            if self._policy.nominatim_enabled and not self._cancel_requested:
                resolver = create_nominatim_location_resolver(
                    database,
                    user_agent=self._user_agent,
                )
                processor = PhotoProcessor(location_resolver=resolver)
                eligible = [
                    photo
                    for photo in photos
                    if LibraryScanner.needs_location_enrichment(photo)
                ]
                total = len(eligible)
                self.phase_progress.emit(
                    ScanProgress(ScanProgressPhase.NOMINATIM, 0, total)
                )
                for index, photo in enumerate(eligible, start=1):
                    if self._cancel_requested:
                        break
                    processor.enrich_location(photo, language=self._language)
                    repository.save(resolve_photo_metadata(photo, self._policy))
                    self.phase_progress.emit(
                        ScanProgress(ScanProgressPhase.NOMINATIM, index, total)
                    )
            self.completed.emit((repository.list_by_source(self._source_id) if self._source_id else repository.list_all()))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            database.close()

    def request_cancel(self) -> None:
        self._cancel_requested = True
