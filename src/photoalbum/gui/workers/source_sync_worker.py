from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.sources import (
    PhotoSource,
    ProjectSource,
    SourceAssetCache,
    SourceImporter,
    PhotoMetadataPolicy,
)


class SourceSyncWorker(QObject):
    """Refresh a remote source snapshot outside the GUI thread."""

    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        project_path: Path,
        source: ProjectSource,
        provider: PhotoSource,
        metadata_policy: PhotoMetadataPolicy | None = None,
        publish_source: bool = False,
    ) -> None:
        super().__init__()
        self._project_path = project_path
        self._source = source
        self._provider = provider
        self._metadata_policy = metadata_policy or PhotoMetadataPolicy.for_source_kind(
            source.kind
        )
        self._publish_source = publish_source

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
                    lambda: database.set_project_metadata(
                        "photo_source",
                        self._source.to_json(),
                        commit=False,
                    )
                    if self._publish_source
                    else None
                ),
            )

        except Exception as exc:
            self.failed.emit(str(exc))
            return

        finally:
            database.close()

        self.completed.emit(result)

    def _handle_progress(
        self,
        current: int,
        total: int,
    ) -> None:
        self.progress.emit(current, total)
