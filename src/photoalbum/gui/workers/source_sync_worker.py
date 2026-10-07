from __future__ import annotations

from pathlib import Path
from dataclasses import replace

from PySide6.QtCore import QObject, Signal, Slot

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.database.source_repository import SourceRepository
from photoalbum.sources import (
    PhotoSource,
    ProjectSource,
    SourceAssetCache,
    SourceImporter,
    PhotoMetadataPolicy,
)
from photoalbum.sources.base import AuthenticationError, SourceError
from photoalbum.sources.operation import SourceOperationResult
from .metadata_refresh_worker import MetadataRefreshWorker


class SourceSyncWorker(QObject):
    """Refresh a remote source snapshot outside the GUI thread."""

    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)
    source_result = Signal(object)
    phase_progress = Signal(object)
    event_received = Signal(object)

    def __init__(
        self,
        *,
        project_path: Path,
        source: ProjectSource,
        provider: PhotoSource,
        metadata_policy: PhotoMetadataPolicy | None = None,
        publish_source: bool = False,
        language: str | None = None,
        user_agent: str = "",
    ) -> None:
        super().__init__()
        self._project_path = project_path
        self._source = source
        self._provider = provider
        self._metadata_policy = metadata_policy or source.effective_metadata_policy
        self._publish_source = publish_source
        self._language = language
        self._user_agent = user_agent

    @Slot()
    def run(self) -> None:
        database = ProjectDatabase(self._project_path)

        try:
            database.initialize()

            # list_assets() happens before SourceImporter knows the total.
            # Keep the UI responsive and explicitly show that source reading
            # has started while the first provider request is in progress.
            self.progress.emit(0, 0)

            result = SourceImporter(
                PhotoRepository(database),
                SourceAssetCache(database.path),
            ).import_collection(
                self._source,
                self._provider,
                on_progress=self._handle_progress,
                metadata_policy=self._metadata_policy,
                on_commit=(
                    lambda: SourceRepository(database).save(
                        self._source,
                        commit=False,
                    )
                    if self._publish_source
                    else None
                ),
            )

        except Exception as exc:
            issue = ("authentication" if isinstance(exc, AuthenticationError)
                     else "access" if isinstance(exc, (SourceError, OSError)) else "metadata")
            self.source_result.emit(SourceOperationResult(self._source.id, "failed", issue, str(exc)))
            self.failed.emit(str(exc))
            return

        finally:
            database.close()

        # Modifying an album must finish the same metadata/geocoding phase
        # as a normal synchronization, after the atomic snapshot publication.
        metadata = MetadataRefreshWorker(
            project_path=self._project_path, source_id=self._source.id,
            policy=self._metadata_policy, language=self._language,
            user_agent=self._user_agent,
        )
        errors, geocoding, refreshed = [], [], []
        metadata.failed.connect(errors.append)
        metadata.geocoding_status.connect(geocoding.append)
        metadata.completed.connect(refreshed.append)
        metadata.phase_progress.connect(self.phase_progress.emit)
        metadata.event_received.connect(self.event_received.emit)
        metadata.run()
        issue = "metadata" if errors else "geocoding" if False in geocoding else None
        self.source_result.emit(SourceOperationResult(
            self._source.id, "partial" if issue else "success", issue,
            errors[-1] if errors else "",
        ))
        if refreshed:
            result = replace(result, photos=tuple(refreshed[-1]))
        self.completed.emit(result)

    def _handle_progress(
        self,
        current: int,
        total: int,
    ) -> None:
        self.progress.emit(current, total)
