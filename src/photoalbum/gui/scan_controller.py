from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QMessageBox

from photoalbum.app_info import user_agent
from photoalbum.app import ProjectService
from photoalbum.gui.widgets.photo_sources_widget import PhotoSourcesWidget
from photoalbum.gui.workers import (
    MetadataRefreshWorker,
    ScanWorker,
    SourceSyncWorker,
)
from photoalbum.i18n import Translator
from photoalbum.scanner import LibraryScanResult, ProcessingEvent, ProcessingEventType
from photoalbum.sources import PhotoMetadataPolicy


class ScanController(QObject):
    """Coordinate a library scan and report its progress in the source tab."""

    error = Signal(str)
    status_message = Signal(str)
    running_changed = Signal(bool)
    photos_ready = Signal(object)
    source_unavailable = Signal()
    source_changed = Signal()

    def __init__(self, project_service: ProjectService, view: PhotoSourcesWidget,
                 translator: Translator, *, language: str, parent=None) -> None:
        super().__init__(parent)
        self._project_service = project_service
        self._view = view
        self._translator = translator
        self._language = language
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | SourceSyncWorker | MetadataRefreshWorker | None = None
        self._operation_kind: str | None = None
        self._source_sync_name: str | None = None
        self._pending_source = None
        self._pending_provider = None
        self.reset()

    @property
    def is_running(self) -> bool:
        return self._scan_thread is not None

    def reset(self) -> None:
        self.analysis_completed = False
        self._scan_total_files = 0

    def toggle(self) -> None:
        """Start a scan or request cancellation of the running scan."""
        if self._scan_thread is None:
            self.start()
            return

        self.cancel()

    def cancel(self) -> None:
        """Request cooperative cancellation of the current scan."""
        worker = self._scan_worker

        if worker is None:
            return

        request_cancel = getattr(
            worker,
            "request_cancel",
            None,
        )

        if not callable(request_cancel):
            return

        request_cancel()

        self._view.analyze_button.setEnabled(False)
        self._view.analyze_button.setText(
            self._translator.tr('main.analysis_stopping_button')
        )

        self._view.summary_label.setText(self._translator.tr('main.analysis_stopping'))

        self.status_message.emit(self._translator.tr('main.analysis_stopping'))

    def start(self) -> None:
        self._start_sources_operation(synchronize=False)

    def sync_source(self) -> None:
        self._start_sources_operation(synchronize=True)

    def _start_sources_operation(self, *, synchronize: bool) -> None:
        from photoalbum.gui.workers.sources_refresh_worker import SourcesRefreshWorker
        if self.is_running:
            return
        if self._project_service.project_path is None:
            self.error.emit(self._translator.tr('main.no_project_error'))
            return
        sources = [source for source in self._project_service.list_sources() if source.enabled]
        if not sources:
            return
        self._operation_kind = "sources"
        self.running_changed.emit(True)
        self._view.prepare_scan_progress(nominatim_enabled=any(
            source.effective_metadata_policy.nominatim_enabled for source in sources))
        thread = QThread(self)
        worker = SourcesRefreshWorker(
            project_path=self._project_service.project_path, sources=sources,
            providers={source.id: self._project_service.get_photo_source_session(source.id) for source in sources},
            synchronize=synchronize, language=self._language, user_agent=user_agent())
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.phase_progress.connect(self._scan_phase_progress)
        worker.source_progress.connect(self._source_sync_progress)
        worker.event_received.connect(self._handle_processing_event)
        worker.log_message.connect(self._view.log_view.appendPlainText)
        worker.completed.connect(self._metadata_refresh_completed)
        worker.failed.connect(self._scan_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._scan_thread_finished)
        self._scan_thread = thread
        self._scan_worker = worker
        thread.start()

    def import_remote_source(self, source, provider) -> None:
        if self._scan_thread is not None:
            return
        self._sync_remote_source(
            source,
            publish_source=True,
            provider=provider,
        )

    def _sync_remote_source(
        self,
        source,
        *,
        publish_source: bool,
        provider=None,
    ) -> None:
        """Refresh a provider snapshot without blocking the GUI thread."""
        project_path = self._project_service.project_path
        if project_path is None:
            self.error.emit(
                self._translator.tr("main.no_project_error")
            )
            return

        provider = provider or self._project_service.get_photo_source_session(source.id)
        if provider is None:
            self.error.emit(
                self._translator.tr(
                    "source.sync.reconnect_required"
                )
            )
            return

        self._source_sync_name = (
            getattr(provider, "label", None)
            or source.provider_label
            or source.kind.replace("-", " ").title()
        )
        self._operation_kind = "source_import" if publish_source else "source_sync"
        self._pending_source = source if publish_source else None
        self._pending_provider = provider if publish_source else None

        self._view.prepare_source_progress(self._source_sync_name)
        self._view.summary_label.setText(
            self._translator.tr("source.sync.running")
        )

        self.running_changed.emit(True)

        # A source synchronization is currently not cancellable midway:
        # the provider/importer contract is snapshot-atomic.
        self._view.analyze_button.setEnabled(False)
        self._view.analyze_button.setText(
            self._translator.tr("source.sync.running_button")
        )

        thread = QThread(self)
        worker = SourceSyncWorker(
            project_path=project_path,
            source=source,
            provider=provider,
            metadata_policy=(
                self._project_service.get_photo_metadata_policy(source.id)
                if not publish_source
                else source.effective_metadata_policy
            ),
            publish_source=publish_source,
        )

        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(
            self._source_sync_progress
        )
        worker.completed.connect(
            self._source_sync_completed
        )
        worker.failed.connect(
            self._source_sync_failed
        )

        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(
            self._scan_thread_finished
        )

        self._scan_thread = thread
        self._scan_worker = worker

        thread.start()

    def _source_sync_progress(
        self,
        current: int,
        total: int,
    ) -> None:
        self._view.update_source_progress(
            current,
            total,
        )

    def _source_sync_completed(self, result) -> None:
        self.analysis_completed = True

        if self._pending_source is not None and self._pending_provider is not None:
            self._project_service.activate_source_session(
                self._pending_source.id,
                self._pending_provider,
            )
            self.source_changed.emit()

        photos = list(result.photos)
        self.photos_ready.emit(photos)

        self._view.summary_label.setText(
            self._translator.tr(
                "source.sync.completed",
                count=len(photos),
            )
        )

        self._view.log_view.appendPlainText(
            self._translator.tr(
                "source.sync.log",
                source=self._source_sync_name or "",
                count=len(photos),
                added=result.added,
                updated=result.updated,
                missing=result.missing,
            )
        )

    def _source_sync_failed(
        self,
        message: str,
    ) -> None:
        self.analysis_completed = False
        if self._pending_provider is not None:
            try:
                self._pending_provider.close()
            except Exception:
                pass
        self._view.summary_label.setText(
            self._translator.tr("source.sync.failed")
        )
        self.error.emit(message)

    def refresh_metadata(self, source_id: str | None = None) -> None:
        if self._scan_thread is not None:
            return
        project_path = self._project_service.project_path
        if project_path is None:
            return
        policy = self._project_service.get_photo_metadata_policy(source_id)
        self._operation_kind = "metadata"
        self._view.prepare_scan_progress(
            nominatim_enabled=policy.nominatim_enabled
        )
        self._view.summary_label.setText(
            self._translator.tr("main.analysis_running")
        )
        self.running_changed.emit(True)
        thread = QThread(self)
        worker = MetadataRefreshWorker(
            project_path=project_path,
            policy=policy,
            source_id=source_id,
            language=self._language,
            user_agent=user_agent(),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.phase_progress.connect(self._scan_phase_progress)
        worker.completed.connect(self._metadata_refresh_completed)
        worker.failed.connect(self._scan_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._scan_thread_finished)
        self._scan_thread = thread
        self._scan_worker = worker
        thread.start()

    def _metadata_refresh_completed(self, photos) -> None:
        self.analysis_completed = True
        self.photos_ready.emit(list(photos))
        message = self._translator.tr(
            "source.metadata.completed", count=len(photos)
        )
        self._view.summary_label.setText(message)
        self.status_message.emit(message)

    def _scan_discovered(self, total: int) -> None:
        """Initialize scan progress after file discovery."""
        self._scan_total_files = max(total, 0)
        self._update_scan_progress(0)

    def _scan_phase_progress(self, progress) -> None:
        """Display progress for one logical scan phase."""
        phase = getattr(progress.phase, "value", progress.phase)

        self._view.update_scan_phase_progress(
            str(phase),
            progress.current,
            progress.total,
        )

    def _scan_progress(self, current: int, total: int) -> None:
        """Update scan progress from the scanner."""
        self._scan_total_files = max(total, 0)
        self._update_scan_progress(current)

    def _update_scan_progress(self, current: int) -> None:
        total = self._scan_total_files

        if total <= 0:
            self._view.progress_bar.setRange(0, 0)
            self._view.progress_bar.setFormat(
                self._translator.tr('main.analysis_in_progress')
            )
            return

        current = min(max(current, 0), total)

        self._view.progress_bar.setRange(0, total)

        self._view.progress_bar.setValue(current)

        self._view.progress_bar.setFormat(
            self._translator.tr('main.progress_photos', current=current, total=total)
        )

        self._view.summary_label.setText(
            self._translator.tr(
                "main.analysis_progress",
                current=current,
                total=total,
                remaining=max(total - current, 0),
            )
        )

    def _handle_processing_event(self, event: ProcessingEvent) -> None:
        message = self._translated_processing_event(event)

        self._view.log_view.appendPlainText(
            f'[{event.type.value}] {event.path.name} : {message}'
        )

    def _translated_processing_event(self, event: ProcessingEvent) -> str:
        keys = {
            ProcessingEventType.ANALYSIS_STARTED:
                "processing.event.analysis_started",
            ProcessingEventType.DATE_FROM_EXIF:
                "processing.event.date_from_exif",
            ProcessingEventType.DATE_FROM_FILENAME:
                "processing.event.date_from_filename",
            ProcessingEventType.DATE_MISSING:
                "processing.event.date_missing",
            ProcessingEventType.GPS_FOUND:
                "processing.event.gps_found",
            ProcessingEventType.GPS_MISSING:
                "processing.event.gps_missing",
            ProcessingEventType.GEOCODING_STARTED:
                "processing.event.geocoding_started",
            ProcessingEventType.LOCATION_FROM_CACHE:
                "processing.event.location_from_cache",
            ProcessingEventType.LOCATION_FROM_REVERSE:
                "processing.event.location_from_reverse",
            ProcessingEventType.LOCATION_NOT_FOUND:
                "processing.event.location_not_found",
            ProcessingEventType.ANALYSIS_COMPLETED:
                "processing.event.analysis_completed",
        }

        if event.type == ProcessingEventType.GEOCODING_ERROR:
            detail = event.message

            prefix = "Geocoding failed:"
            if detail.startswith(prefix):
                detail = detail[len(prefix):].strip()

            return self._translator.tr('processing.event.geocoding_error', error=detail)

        key = keys.get(event.type)

        if key is None:
            return event.message

        return self._translator.tr(key)

    def _scan_completed(self, result: LibraryScanResult) -> None:
        statistics = result.statistics

        if result.cancelled:
            self.analysis_completed = False

            self._view.summary_label.setText(
                self._translator.tr('main.analysis_cancelled')
            )

            self.status_message.emit(self._translator.tr('main.analysis_cancelled'))
        else:
            self._update_scan_progress(self._scan_total_files)
            self.analysis_completed = True

        all_photos = [*result.photos, *result.date_anomalies]

        all_photos.sort(
            key=lambda photo: (
                photo.capture_datetime is None,
                photo.capture_datetime or datetime.max,
                photo.filename.lower(),
            )
        )

        self.photos_ready.emit(all_photos)

        if result.missing_photos:
            self._view.log_view.appendPlainText('')

            self._view.log_view.appendPlainText(
                self._translator.tr(
                    (
                        "main.missing_photos_log_header_one"
                        if len(result.missing_photos) == 1
                        else "main.missing_photos_log_header_many"
                    ),
                    count=len(result.missing_photos),
                )
            )

            for photo in result.missing_photos:
                self._view.log_view.appendPlainText(
                    self._translator.tr('main.missing_photo_log', path=photo.path)
                )

            QMessageBox.warning(
                self._view,
                self._translator.tr('main.missing_photos_title'),
                self._translator.tr(
                    (
                        "main.missing_photos_warning_one"
                        if len(result.missing_photos) == 1
                        else "main.missing_photos_warning_many"
                    ),
                    count=len(result.missing_photos),
                ),
            )

        statistics_text = " | ".join(
            [
                self._translator.tr('main.discovered', count=statistics.discovered),
                self._translator.tr('main.analyzed', count=statistics.analyzed),
                self._translator.tr('main.reused', count=statistics.reused),
                self._translator.tr('main.geocoded', count=statistics.geocoded),
                self._translator.tr('main.date_anomalies', count=statistics.date_anomalies),
                self._translator.tr('main.errors', count=statistics.errors),
            ]
        )

        if result.cancelled:
            self._view.summary_label.setText(
                self._translator.tr('main.analysis_cancelled') + ' ' + statistics_text
            )
        else:
            self._view.summary_label.setText(statistics_text)

        if result.date_anomalies:
            self._view.log_view.appendPlainText("")
            self._view.log_view.appendPlainText(
                self._translator.tr('main.photos_requiring_date')
            )

            for photo in result.date_anomalies:
                self._view.log_view.appendPlainText(str(photo.path))

        if not result.cancelled:
            self.status_message.emit(self._translator.tr('main.analysis_completed'))

    def _scan_failed(self, message: str) -> None:
        self._view.summary_label.setText(self._translator.tr('main.analysis_failed'))

        self.error.emit(message)

    def _scan_thread_finished(self) -> None:
        thread = self._scan_thread
        if thread is not None:
            # finished can arrive before native thread cleanup has completed.
            thread.wait()
        self._scan_worker = None
        self._scan_thread = None
        self._operation_kind = None
        self._source_sync_name = None
        self._pending_source = None
        self._pending_provider = None

        if thread is not None:
            thread.deleteLater()

        self._view.finish_processing_progress()
        self.running_changed.emit(False)

        if self._project_service.is_open and self._view.has_active_sources:
            self._view.analyze_button.setText(
                self._translator.tr('sources.analyze')
            )
