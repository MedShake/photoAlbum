from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from photoalbum.app.project_scan_service import ProjectScanService
from photoalbum.database import ProjectDatabase, PhotoRepository
from photoalbum.sources import SourceImporter, SourceAssetCache
from photoalbum.i18n import Translator
from .metadata_refresh_worker import MetadataRefreshWorker


class SourcesRefreshWorker(QObject):
    """Sequential source jobs; a failed provider never rolls back another one."""

    completed = Signal(object)
    failed = Signal(str)
    log_message = Signal(str)
    phase_progress = Signal(object)
    event_received = Signal(object)
    source_progress = Signal(int, int)

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
                break
            self.log_message.emit(f"{source.provider_label or source.kind} — {source.collection_name}")
            try:
                if source.kind == "local":
                    result = ProjectScanService().scan(
                        project_path=self._path, source_id=source.id,
                        source_directory=Path(str(source.config["directory"])),
                        recursive=bool(source.config.get("recursive", False)),
                        metadata_policy=source.effective_metadata_policy,
                        language=self._language, user_agent=self._user_agent,
                        should_cancel=lambda: self._cancelled,
                        on_event=self.event_received.emit,
                        on_phase_progress=self.phase_progress.emit,
                    )
                    for error in result.errors:
                        self.log_message.emit(
                            translator.tr(
                                "sources.refresh.file_failed",
                                source=source.name,
                                filename=error.path.name,
                            )
                        )
                    continue
                if self._synchronize:
                    provider = self._providers.get(source.id)
                    if provider is None:
                        raise RuntimeError(translator.tr("sources.reconnect_required"))
                    database = ProjectDatabase(self._path)
                    try:
                        database.initialize()
                        SourceImporter(PhotoRepository(database), SourceAssetCache(self._path)).import_collection(
                            source, provider, on_progress=self.source_progress.emit)
                    finally:
                        database.close()
                self._current = MetadataRefreshWorker(
                    project_path=self._path, source_id=source.id,
                    policy=source.effective_metadata_policy,
                    language=self._language, user_agent=self._user_agent,
                )
                self._current.phase_progress.connect(self.phase_progress.emit)
                self._current.failed.connect(
                    lambda _message, source_name=source.name: self.log_message.emit(
                        translator.tr("sources.refresh.source_failed", source=source_name)
                    )
                )
                self._current.run()
                self._current = None
            except Exception:
                self.log_message.emit(
                    "⚠ " + translator.tr(
                        "sources.refresh.source_failed",
                        source=source.name,
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
