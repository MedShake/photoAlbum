from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from photoalbum.app.project_scan_service import ProjectScanService
from photoalbum.database import ProjectDatabase, PhotoRepository
from photoalbum.sources import SourceImporter, SourceAssetCache
from photoalbum.i18n import Translator
from photoalbum.sources.base import AuthenticationError, SourceError
from photoalbum.sources.operation import SourceOperationResult
from photoalbum.scanner import ProcessingEventType
from .metadata_refresh_worker import MetadataRefreshWorker


class SourcesRefreshWorker(QObject):
    """Sequential source jobs; a failed provider never rolls back another one."""

    completed = Signal(object)
    failed = Signal(str)
    log_message = Signal(str)
    phase_progress = Signal(object)
    event_received = Signal(object)
    source_progress = Signal(int, int)
    source_result = Signal(object)

    def __init__(self, *, project_path, sources, providers, synchronize,
                 language, user_agent):
        super().__init__()
        self._path = project_path
        self._sources = tuple(source for source in sources if source.enabled)
        self._providers = dict(providers)
        self._synchronize = synchronize
        self._language = language
        self._user_agent = user_agent
        self._cancelled = False
        self._current = None

    def request_cancel(self):
        self._cancelled = True
        if self._current is not None:
            self._current.request_cancel()

    @Slot()
    def run(self):
        translator = Translator(self._language)
        for source in self._sources:
            if self._cancelled:
                self.source_result.emit(SourceOperationResult(source.id, "cancelled"))
                break
            provider_name = (
                translator.tr("sources.local_folder")
                if source.kind == "local"
                else (source.provider_label or source.kind.replace("-", " ").title())
            )
            source_name = f"{provider_name} — {source.collection_name}"
            operation_prefix = "sources.sync" if self._synchronize else "sources.refresh_one"
            self.log_message.emit(
                translator.tr(f"{operation_prefix}.started", source=source_name)
            )
            try:
                if source.kind == "local":
                    geocoding_errors = []

                    def record_event(event):
                        if event.type == ProcessingEventType.GEOCODING_ERROR:
                            geocoding_errors.append(event.message)
                        self.event_received.emit(event)

                    result = ProjectScanService().scan(
                        project_path=self._path, source_id=source.id,
                        source_directory=Path(str(source.config["directory"])),
                        recursive=bool(source.config.get("recursive", False)),
                        metadata_policy=source.effective_metadata_policy,
                        language=self._language, user_agent=self._user_agent,
                        should_cancel=lambda: self._cancelled,
                        on_event=record_event,
                        on_phase_progress=self.phase_progress.emit,
                    )
                    for error in result.errors:
                        self.log_message.emit(
                            translator.tr(
                                "sources.refresh.file_failed",
                                source=source.collection_name,
                                filename=error.path.name,
                            )
                        )
                    self.log_message.emit(
                        translator.tr(
                            "sources.sync.local_summary",
                            source=source_name,
                            discovered=result.statistics.discovered,
                            analyzed=result.statistics.analyzed,
                            reused=result.statistics.reused,
                            missing=len(result.missing_photos),
                        )
                    )
                    if result.cancelled or self._cancelled:
                        self.source_result.emit(SourceOperationResult(source.id, "cancelled"))
                        self.log_message.emit(
                            translator.tr("sources.processing_cancelled", source=source_name)
                        )
                        break
                    if result.errors or geocoding_errors:
                        issue = "metadata" if result.errors else "geocoding"
                        self.source_result.emit(SourceOperationResult(source.id, "partial", issue))
                        key = "sources.operation.partial" if result.errors else "sources.geocoding_incomplete"
                        self.log_message.emit("⚠ " + translator.tr(key, source=source_name))
                        continue
                    self.source_result.emit(SourceOperationResult(source.id, "success"))
                    self.log_message.emit(
                        translator.tr(f"{operation_prefix}.completed", source=source_name)
                    )
                    continue
                if self._synchronize:
                    provider = self._providers.get(source.id)
                    if provider is None:
                        raise RuntimeError(translator.tr("sources.reconnect_required"))
                    database = ProjectDatabase(self._path)
                    try:
                        database.initialize()
                        import_result = SourceImporter(
                            PhotoRepository(database), SourceAssetCache(self._path)
                        ).import_collection(
                            source, provider, on_progress=self.source_progress.emit
                        )
                    finally:
                        database.close()
                    self.log_message.emit(
                        translator.tr(
                            "sources.sync.remote_summary",
                            source=source_name,
                            count=len(import_result.photos),
                            added=import_result.added,
                            updated=import_result.updated,
                            missing=import_result.missing,
                        )
                    )
                self._current = MetadataRefreshWorker(
                    project_path=self._path, source_id=source.id,
                    policy=source.effective_metadata_policy,
                    language=self._language, user_agent=self._user_agent,
                )
                self._current.phase_progress.connect(self.phase_progress.emit)
                self._current.event_received.connect(self.event_received.emit)
                metadata_errors = []
                metadata_cancelled = []
                geocoding_statuses = []
                self._current.failed.connect(metadata_errors.append)
                self._current.cancelled.connect(metadata_cancelled.append)
                self._current.geocoding_status.connect(geocoding_statuses.append)
                self._current.run()
                self._current = None
                if metadata_cancelled:
                    self.source_result.emit(SourceOperationResult(source.id, "cancelled"))
                    self.log_message.emit(
                        translator.tr("sources.processing_cancelled", source=source_name)
                    )
                    break
                if metadata_errors:
                    self.source_result.emit(SourceOperationResult(
                        source.id, "partial" if self._synchronize else "failed", "metadata", metadata_errors[-1]
                    ))
                    self.log_message.emit(
                        "⚠ " + translator.tr(
                            f"{operation_prefix}.failed",
                            source=source_name,
                            error=metadata_errors[-1],
                        )
                    )
                    continue
                if False in geocoding_statuses:
                    self.source_result.emit(SourceOperationResult(source.id, "partial", "geocoding"))
                    self.log_message.emit(
                        "⚠ " + translator.tr("sources.geocoding_incomplete", source=source_name)
                    )
                    continue
                self.source_result.emit(SourceOperationResult(source.id, "success"))
                self.log_message.emit(
                    translator.tr(f"{operation_prefix}.completed", source=source_name)
                )
            except Exception as exc:
                issue = ("authentication" if isinstance(exc, AuthenticationError)
                         else "access" if isinstance(exc, (OSError, SourceError)) else "metadata")
                self.source_result.emit(SourceOperationResult(source.id, "failed", issue, str(exc)))
                self.log_message.emit(
                    "⚠ " + translator.tr(
                        f"{operation_prefix}.failed",
                        source=source_name,
                        error=str(exc),
                    )
                )
        database = ProjectDatabase(self._path)
        try:
            active = {source.id for source in self._sources}
            photos = [photo for photo in PhotoRepository(database).list_all() if photo.source_id in active]
            self.completed.emit(photos)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            database.close()
