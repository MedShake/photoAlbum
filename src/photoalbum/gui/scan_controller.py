from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QMessageBox

from photoalbum import __version__
from photoalbum.app import ProjectService
from photoalbum.gui.widgets.photo_sources_widget import PhotoSourcesWidget
from photoalbum.gui.workers import ScanWorker
from photoalbum.i18n import Translator
from photoalbum.scanner import LibraryScanResult, ProcessingEvent, ProcessingEventType


class ScanController(QObject):
    """Coordinate a library scan and report its progress in the source tab."""

    error = Signal(str)
    status_message = Signal(str)
    running_changed = Signal(bool)
    photos_ready = Signal(object)
    source_unavailable = Signal()

    def __init__(self, project_service: ProjectService, view: PhotoSourcesWidget,
                 translator: Translator, *, language: str, parent=None) -> None:
        super().__init__(parent)
        self._project_service = project_service
        self._view = view
        self._translator = translator
        self._language = language
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None
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

        worker.request_cancel()

        self._view.analyze_button.setEnabled(False)
        self._view.analyze_button.setText(
            self._translator.tr('main.analysis_stopping_button')
        )

        self._view.summary_label.setText(self._translator.tr('main.analysis_stopping'))

        self.status_message.emit(self._translator.tr('main.analysis_stopping'))

    def start(self) -> None:
        if self._scan_thread is not None:
            return

        project_path = self._project_service.project_path

        if project_path is None:
            self.error.emit(self._translator.tr('main.no_project_error'))
            return

        source_directory = self._project_service.get_source_directory()
        if source_directory is None:
            self.error.emit(self._translator.tr('main.choose_source_error'))
            return

        if not source_directory.exists():
            message = self._translator.tr('main.source_missing_error', path=source_directory)

            if self._view.log_view.document().blockCount() > 1:
                self._view.log_view.appendPlainText('')

            self._view.log_view.appendPlainText(
                "────────────────────────────────────────"
            )
            self._view.log_view.appendPlainText(f'⚠ {message}')
            self._view.log_view.appendPlainText(
                "────────────────────────────────────────"
            )

            self._view.summary_label.setText(message)

            self.error.emit(message)

            # The source folder is unavailable: Photos is the
            # only meaningful tab until the source is fixed.
            self.running_changed.emit(False)

            self.source_unavailable.emit()

            return

        # Keep the analysis log for the whole project session.
        # A new scan starts a new section instead of erasing
        # previous events.
        if self._view.log_view.document().blockCount() > 1:
            self._view.log_view.appendPlainText('')

        self._view.log_view.appendPlainText('────────────────────────────────────────')
        self._view.log_view.appendPlainText(
            self._translator.tr('main.analysis_log_header', path=source_directory)
        )
        self._view.log_view.appendPlainText('────────────────────────────────────────')

        self._view.summary_label.setText(self._translator.tr('main.analysis_running'))

        self.running_changed.emit(True)

        thread = QThread(self)

        worker = ScanWorker(
            project_path=project_path,
            source_directory=source_directory,
            recursive=self._project_service.get_recursive_scan(),
            language=self._language,
            geocode=True,
            user_agent=f"PhotoAlbum/{__version__}",
        )

        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.event_received.connect(self._handle_processing_event)
        worker.discovered.connect(self._scan_discovered)
        worker.progress.connect(self._scan_progress)
        worker.completed.connect(self._scan_completed)
        worker.failed.connect(self._scan_failed)

        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._scan_thread_finished)

        self._scan_thread = thread
        self._scan_worker = worker

        thread.start()

    def _scan_discovered(self, total: int) -> None:
        """Initialize scan progress after file discovery."""
        self._scan_total_files = max(total, 0)
        self._update_scan_progress(0)

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
        if thread is not None:
            thread.deleteLater()

        self.running_changed.emit(False)

        if self._project_service.is_open and bool(self._view.source_edit.text()):
            self._view.analyze_button.setText(
                self._translator.tr('main.analyze_again')
            )
