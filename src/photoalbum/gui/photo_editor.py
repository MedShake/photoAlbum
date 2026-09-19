from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDateTimeEdit, QDoubleSpinBox,
    QFormLayout, QLabel, QPushButton, QVBoxLayout,
)

from photoalbum import __version__
from photoalbum.app import ProjectService
from photoalbum.gui.workers import GpsGeocodingWorker
from photoalbum.i18n import Translator
from photoalbum.i18n.date_formatter import datetime_edit_format, format_datetime
from photoalbum.models import Photo


class PhotoEditor(QObject):
    """Edit source metadata and resolve GPS changes through the project service."""

    error = Signal(str)
    log_message = Signal(str)
    photos_changed = Signal()

    def __init__(self, project_service: ProjectService, translator: Translator,
                 *, language: str, parent=None) -> None:
        super().__init__(parent)
        self._project_service = project_service
        self._translator = translator
        self._language = language
        self._dialog_parent = parent
        self._gps_thread: QThread | None = None
        self._gps_worker: GpsGeocodingWorker | None = None
        self._gps_photo_path: Path | None = None

    @property
    def is_running(self) -> bool:
        return self._gps_thread is not None

    def edit_datetime(self, photo: Photo) -> None:
        dialog = QDialog(self._dialog_parent)
        dialog.setWindowTitle(self._translator.tr('photos.datetime.title'))

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        filename_label = QLabel(photo.filename)
        filename_label.setWordWrap(True)

        date_time_edit = QDateTimeEdit(dialog)
        date_time_edit.setCalendarPopup(True)
        date_time_edit.setDisplayFormat(datetime_edit_format())
        date_time_edit.setDateTime(photo.capture_datetime or datetime.now())

        form.addRow(self._translator.tr('photos.datetime.photo'), filename_label)
        form.addRow(self._translator.tr('photos.datetime.value'), date_time_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )

        restore_button = buttons.addButton(
            self._translator.tr('photos.datetime.restore'),
            QDialogButtonBox.ButtonRole.ResetRole,
        )

        original_datetime = photo.original_capture_datetime

        restore_button.setEnabled(
            original_datetime is not None and photo.capture_datetime != original_datetime
        )

        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)

        if save_button is not None:
            save_button.setText(self._translator.tr('photos.datetime.save'))

        if cancel_button is not None:
            cancel_button.setText(self._translator.tr('photos.datetime.cancel'))

        restore_requested = False

        def restore_original_datetime() -> None:
            nonlocal restore_requested
            restore_requested = True
            dialog.accept()

        restore_button.clicked.connect(restore_original_datetime)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        old_datetime = photo.capture_datetime

        if restore_requested:
            if original_datetime is None:
                return

            try:
                self._project_service.restore_original_capture_datetime(photo.path)
            except Exception as exc:
                self.error.emit(str(exc))
                return

            old_date_text = (
                format_datetime(old_datetime, include_seconds=True)
                if old_datetime is not None
                else self._translator.tr('photos.datetime.no_date')
            )

            self.log_message.emit(
                self._translator.tr(
                    "photos.datetime.log_restored",
                    filename=photo.filename,
                    old_date=old_date_text,
                    original_date=format_datetime(original_datetime, include_seconds=True),
                )
            )

            self.photos_changed.emit()
            return
        new_datetime = date_time_edit.dateTime().toPython()

        try:
            self._project_service.set_manual_capture_datetime(photo.path, new_datetime)
        except Exception as exc:
            self.error.emit(str(exc))
            return

        new_date_text = format_datetime(new_datetime, include_seconds=True)

        if old_datetime is None:
            log_message = self._translator.tr(
                "photos.datetime.log_added",
                filename=photo.filename,
                new_date=new_date_text,
            )
        else:
            log_message = self._translator.tr(
                "photos.datetime.log_changed",
                filename=photo.filename,
                old_date=format_datetime(old_datetime, include_seconds=True),
                new_date=new_date_text,
            )

        self.log_message.emit(log_message)

        self.photos_changed.emit()

    def edit_gps(self, photo: Photo) -> None:
        dialog = QDialog(self._dialog_parent)
        dialog.setWindowTitle(self._translator.tr('photos.gps.title'))

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        filename_label = QLabel(photo.filename)
        filename_label.setWordWrap(True)

        latitude_edit = QDoubleSpinBox(dialog)
        latitude_edit.setDecimals(7)
        latitude_edit.setRange(-90.0, 90.0)
        latitude_edit.setSingleStep(0.0001)

        longitude_edit = QDoubleSpinBox(dialog)
        longitude_edit.setDecimals(7)
        longitude_edit.setRange(-180.0, 180.0)
        longitude_edit.setSingleStep(0.0001)

        if photo.latitude is not None:
            latitude_edit.setValue(photo.latitude)

        if photo.longitude is not None:
            longitude_edit.setValue(photo.longitude)

        form.addRow(self._translator.tr('photos.gps.photo'), filename_label)
        form.addRow(self._translator.tr('photos.gps.latitude'), latitude_edit)
        form.addRow(self._translator.tr('photos.gps.longitude'), longitude_edit)

        layout.addLayout(form)

        restore_button = QPushButton(self._translator.tr('photos.gps.restore'), dialog)

        has_original_gps = (
            photo.original_latitude is not None and photo.original_longitude is not None
        )

        restore_button.setEnabled(has_original_gps)

        if has_original_gps:
            layout.addWidget(restore_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )

        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)

        if save_button is not None:
            save_button.setText(self._translator.tr('photos.gps.save'))

        if cancel_button is not None:
            cancel_button.setText(self._translator.tr('photos.gps.cancel'))

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        restore_requested = False

        def request_restore() -> None:
            nonlocal restore_requested
            restore_requested = True
            dialog.accept()

        restore_button.clicked.connect(request_restore)

        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        old_latitude = photo.latitude
        old_longitude = photo.longitude

        try:
            if restore_requested:
                self._project_service.restore_original_gps(photo.path)

                latitude = photo.original_latitude
                longitude = photo.original_longitude

                action_key = "photos.gps.log_restored"
            else:
                latitude = latitude_edit.value()
                longitude = longitude_edit.value()

                self._project_service.set_manual_gps(photo.path, latitude, longitude)

                action_key = "photos.gps.log_changed"

        except Exception as exc:
            self.error.emit(str(exc))
            return

        self.log_message.emit(
            self._translator.tr(
                action_key,
                filename=photo.filename,
                old_latitude='—' if old_latitude is None else f'{old_latitude:.7f}',
                old_longitude='—' if old_longitude is None else f'{old_longitude:.7f}',
                latitude=f"{latitude:.7f}",
                longitude=f"{longitude:.7f}",
            )
        )

        self.photos_changed.emit()

        self._start_gps_geocoding(photo.path, latitude, longitude)

    def _start_gps_geocoding(self, photo_path: Path, latitude: float, longitude: float) -> None:
        if self._gps_thread is not None:
            self.log_message.emit(self._translator.tr('photos.gps.geocoding_busy'))
            return

        project_path = self._project_service.project_path

        if project_path is None:
            return

        thread = QThread(self)

        worker = GpsGeocodingWorker(
            project_path=project_path,
            latitude=latitude,
            longitude=longitude,
            language=self._language,
            user_agent=f"PhotoAlbum/{__version__}",
        )

        worker.moveToThread(thread)

        self._gps_photo_path = Path(photo_path)

        thread.started.connect(worker.run)

        worker.completed.connect(self._gps_geocoding_completed)
        worker.failed.connect(self._gps_geocoding_failed)

        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._gps_geocoding_thread_finished)

        self._gps_thread = thread
        self._gps_worker = worker

        self.log_message.emit(self._translator.tr('photos.gps.geocoding_started'))

        thread.start()

    def _gps_geocoding_completed(self, location) -> None:
        photo_path = self._gps_photo_path

        if photo_path is None:
            return

        if location is None:
            self.log_message.emit(self._translator.tr('photos.gps.geocoding_not_found'))
            return

        try:
            self._project_service.set_geocoded_location(
                photo_path,
                place_name=location.place_name,
                city=location.city,
                address=location.address,
                raw_location_data=location.raw_data,
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return

        self.log_message.emit(
            self._translator.tr(
                "photos.gps.geocoding_completed",
                city=location.city or "—",
                address=location.address or "—",
            )
        )

        self.photos_changed.emit()

    def _gps_geocoding_failed(self, error: str) -> None:
        self.log_message.emit(self._translator.tr('photos.gps.geocoding_failed', error=error))

    def _gps_geocoding_thread_finished(self) -> None:
        thread = self._gps_thread
        if thread is not None:
            # finished can arrive before native thread cleanup has completed.
            thread.wait()
        self._gps_worker = None
        self._gps_thread = None
        if thread is not None:
            thread.deleteLater()
        self._gps_photo_path = None

    def open_in_os(self, photo: Photo) -> None:
        path = Path(photo.path)

        if not path.exists():
            self.error.emit(self._translator.tr('photos.open_image.not_found', path=path))
            return

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

        if not opened:
            self.error.emit(self._translator.tr('photos.open_image.error', path=path))
