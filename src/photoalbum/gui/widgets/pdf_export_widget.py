from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QGroupBox,
    QLineEdit, QPushButton, QRadioButton, QComboBox, QProgressBar,
    QPlainTextEdit, QFileDialog, QMessageBox,
)

from photoalbum.album import (
    AlbumBuildResult,
    AlbumStructureSettings,
)
from photoalbum.app import ProjectService
from photoalbum.export import (
    PdfExportContent,
    PdfExportService,
    PdfMetadata,
)
from photoalbum.gui.workers import PdfExportWorker
from photoalbum.project_metadata import PdfExportSettings, ProjectPdfMetadata
from photoalbum.i18n import Translator


class PdfExportWidget(QWidget):
    """PDF options, progress and worker lifetime, independent of the main window."""

    error = Signal(str)
    status_message = Signal(str, int)

    def __init__(
        self, *, translator: Translator, project_service: ProjectService,
        settings_provider: Callable[[], AlbumStructureSettings],
        result_provider: Callable[[], AlbumBuildResult | None],
        before_export: Callable[[], None], parent=None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._project_service = project_service
        self._settings_provider = settings_provider
        self._result_provider = result_provider
        self._before_export = before_export
        self._pdf_thread: QThread | None = None
        self._loading_project_settings = False
        self._pdf_worker: PdfExportWorker | None = None
        self._create_content()
        self.update_summary()

    @property
    def is_running(self) -> bool:
        return self._pdf_thread is not None

    def _create_content(self) -> None:
        render_layout = QVBoxLayout(self)

        # Export content.
        content_group = QGroupBox(self._translator.tr('render.content_group'))
        content_layout = QVBoxLayout(content_group)

        self._pdf_content_complete_radio = QRadioButton(
            self._translator.tr('render.content_complete')
        )
        self._pdf_content_covers_radio = QRadioButton(
            self._translator.tr('render.content_covers')
        )
        self._pdf_content_body_radio = QRadioButton(self._translator.tr('render.content_body'))

        self._pdf_content_complete_radio.setChecked(True)

        for radio in (
            self._pdf_content_complete_radio,
            self._pdf_content_covers_radio,
            self._pdf_content_body_radio,
        ):
            radio.toggled.connect(self.update_summary)
            radio.toggled.connect(self._save_project_settings)
            content_layout.addWidget(radio)

        render_layout.addWidget(content_group)

        # Quality.
        quality_group = QGroupBox(self._translator.tr('render.quality_group'))
        quality_layout = QFormLayout(quality_group)

        self._pdf_dpi_combo = QComboBox()

        self._pdf_dpi_combo.addItem(self._translator.tr('render.dpi_screen'), 96)
        self._pdf_dpi_combo.addItem(self._translator.tr('render.dpi_good'), 150)
        self._pdf_dpi_combo.addItem(self._translator.tr('render.dpi_print'), 300)
        self._pdf_dpi_combo.addItem(self._translator.tr('render.dpi_high'), 600)

        self._pdf_dpi_combo.setCurrentIndex(2)
        self._pdf_dpi_combo.currentIndexChanged.connect(self.update_summary)
        self._pdf_dpi_combo.currentIndexChanged.connect(self._save_project_settings)

        quality_layout.addRow(self._translator.tr('render.resolution'), self._pdf_dpi_combo)

        self._pdf_pixel_size_label = QLabel()
        self._pdf_pixel_size_label.setWordWrap(True)

        quality_layout.addRow(
            self._translator.tr('render.pixel_size'),
            self._pdf_pixel_size_label,
        )

        render_layout.addWidget(quality_group)

        # PDF metadata.
        metadata_group = QGroupBox(self._translator.tr('render.metadata_group'))
        metadata_layout = QFormLayout(metadata_group)

        self._pdf_title_edit = QLineEdit()
        self._pdf_author_edit = QLineEdit()
        self._pdf_subject_edit = QLineEdit()
        self._pdf_keywords_edit = QLineEdit()

        metadata_layout.addRow(
            self._translator.tr('render.metadata_title'),
            self._pdf_title_edit,
        )
        metadata_layout.addRow(
            self._translator.tr('render.metadata_author'),
            self._pdf_author_edit,
        )
        metadata_layout.addRow(
            self._translator.tr('render.metadata_subject'),
            self._pdf_subject_edit,
        )
        metadata_layout.addRow(
            self._translator.tr('render.metadata_keywords'),
            self._pdf_keywords_edit,
        )

        for editor in (
            self._pdf_title_edit,
            self._pdf_author_edit,
            self._pdf_subject_edit,
            self._pdf_keywords_edit,
        ):
            editor.editingFinished.connect(self._save_project_settings)

        render_layout.addWidget(metadata_group)

        # Document summary.
        document_group = QGroupBox(self._translator.tr('render.document_group'))
        document_layout = QFormLayout(document_group)

        self._pdf_format_label = QLabel()
        self._pdf_pages_label = QLabel()
        self._pdf_photos_label = QLabel()

        document_layout.addRow(
            self._translator.tr('render.document_format'),
            self._pdf_format_label,
        )
        document_layout.addRow(
            self._translator.tr('render.document_pages'),
            self._pdf_pages_label,
        )
        document_layout.addRow(
            self._translator.tr('render.document_photos'),
            self._pdf_photos_label,
        )

        render_layout.addWidget(document_group)

        # Output file: keep the destination next to the final generate action.
        output_group = QGroupBox(self._translator.tr('render.output_group'))
        output_layout = QHBoxLayout(output_group)

        self._pdf_output_edit = QLineEdit()
        self._pdf_output_edit.setPlaceholderText(
            self._translator.tr('render.output_placeholder')
        )

        self._pdf_output_button = QPushButton(self._translator.tr('render.browse'))
        self._pdf_output_button.clicked.connect(self._choose_pdf_output)

        output_layout.addWidget(self._pdf_output_edit, 1)
        output_layout.addWidget(self._pdf_output_button)

        render_layout.addWidget(output_group)

        self._pdf_progress_bar = QProgressBar()
        self._pdf_progress_bar.setRange(0, 1)
        self._pdf_progress_bar.setValue(0)
        self._pdf_progress_bar.setFormat('%v / %m pages — %p%')
        self._pdf_progress_bar.setVisible(False)

        render_layout.addWidget(self._pdf_progress_bar)

        self._pdf_log_view = QPlainTextEdit()
        self._pdf_log_view.setReadOnly(True)
        self._pdf_log_view.setMaximumBlockCount(2000)
        self._pdf_log_view.setVisible(False)

        self._pdf_log_view.setMaximumHeight(280)

        render_layout.addWidget(self._pdf_log_view)

        render_layout.addStretch(1)

        action_layout = QHBoxLayout()
        action_layout.addStretch(1)

        self.generate_button = QPushButton(self._translator.tr('render.generate'))

        self.generate_button.clicked.connect(self.generate)

        action_layout.addWidget(self.generate_button)

        render_layout.addLayout(action_layout)


    def set_project_settings(self, settings: PdfExportSettings | None) -> None:
        """Load persisted PDF preferences without writing them back."""
        if settings is None:
            settings = PdfExportSettings()

        self._loading_project_settings = True
        try:
            index = self._pdf_dpi_combo.findData(settings.dpi)
            self._pdf_dpi_combo.setCurrentIndex(index if index >= 0 else 2)

            self._pdf_content_complete_radio.setChecked(
                settings.content == PdfExportContent.COMPLETE.value
            )
            self._pdf_content_covers_radio.setChecked(
                settings.content == PdfExportContent.COVERS.value
            )
            self._pdf_content_body_radio.setChecked(
                settings.content == PdfExportContent.BODY.value
            )

            self._pdf_title_edit.setText(settings.metadata.title)
            self._pdf_author_edit.setText(settings.metadata.author)
            self._pdf_subject_edit.setText(settings.metadata.subject)
            self._pdf_keywords_edit.setText(settings.metadata.keywords)
        finally:
            self._loading_project_settings = False

        self.update_summary()

    def project_settings(self) -> PdfExportSettings:
        if self._pdf_content_covers_radio.isChecked():
            content = PdfExportContent.COVERS.value
        elif self._pdf_content_body_radio.isChecked():
            content = PdfExportContent.BODY.value
        else:
            content = PdfExportContent.COMPLETE.value

        return PdfExportSettings(
            metadata=ProjectPdfMetadata(
                title=self._pdf_title_edit.text().strip(),
                author=self._pdf_author_edit.text().strip(),
                subject=self._pdf_subject_edit.text().strip(),
                keywords=self._pdf_keywords_edit.text().strip(),
            ),
            dpi=int(self._pdf_dpi_combo.currentData()),
            content=content,
        )

    def save_project_settings(self) -> None:
        if self._loading_project_settings or not self._project_service.is_open:
            return
        self._project_service.set_pdf_export_settings(self.project_settings())

    def _save_project_settings(self, *args) -> None:
        self.save_project_settings()

    def _choose_pdf_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._translator.tr('render.output_dialog'),
            self._pdf_output_edit.text(),
            "PDF (*.pdf)",
        )

        if not path:
            return

        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        self._pdf_output_edit.setText(path)

    def update_summary(self) -> None:
        if not hasattr(self, '_pdf_format_label'):
            return

        try:
            settings = self._settings_provider()
        except Exception:
            return

        page_format = settings.effective_page_format()

        format_name = self._translator.tr("album.custom_format") if settings.page_format == "custom" else page_format.name
        width_mm = page_format.width_mm
        height_mm = page_format.height_mm

        dpi = int(self._pdf_dpi_combo.currentData())

        width_px = round(width_mm / 25.4 * dpi)
        height_px = round(height_mm / 25.4 * dpi)

        self._pdf_format_label.setText(f'{format_name} — {width_mm:g} × {height_mm:g} mm')

        self._pdf_pixel_size_label.setText(
            self._translator.tr(
                "render.pixel_dimensions",
                width=width_px,
                height=height_px,
                dpi=dpi,
            )
        )

        photos = []

        if self._project_service.is_open:
            photos = self._project_service.list_album_photos()

        self._pdf_photos_label.setText(str(len(photos)))

        result = self._result_provider()

        if result is None:
            self._pdf_pages_label.setText(self._translator.tr('render.page_count_pending'))
        else:
            self._pdf_pages_label.setText(str(result.total_page_count))

    def generate(self) -> None:
        if self._pdf_thread is not None:
            return

        if not self._project_service.is_open:
            self.error.emit(self._translator.tr('main.no_project_error'))
            return

        self._before_export()

        result = self._result_provider()

        if result is None:
            self.error.emit(self._translator.tr('render.no_album'))
            return

        output_text = self._pdf_output_edit.text().strip()

        if not output_text:
            self.error.emit(self._translator.tr('render.output_required'))
            return

        output_path = Path(output_text)

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix('.pdf')

        try:
            settings = self._settings_provider()

            page_format = settings.effective_page_format()

            width_mm = page_format.width_mm
            height_mm = page_format.height_mm

            pdf_settings = self.project_settings()
            dpi = pdf_settings.dpi

            photos = self._project_service.list_album_photos()
            export_content = PdfExportContent(pdf_settings.content)
            metadata = PdfMetadata(
                title=pdf_settings.metadata.title,
                author=pdf_settings.metadata.author,
                subject=pdf_settings.metadata.subject,
                keywords=pdf_settings.metadata.keywords,
            )
            self._project_service.set_pdf_export_settings(pdf_settings)

        except Exception as exc:
            self.error.emit(self._translator.tr('render.generate_error', error=exc))
            return

        body_page_count = len(result.pagination.pages)

        if export_content == PdfExportContent.COVERS:
            total_pages = 4
        elif export_content == PdfExportContent.BODY:
            total_pages = body_page_count
        else:
            total_pages = body_page_count + 4

        print_settings = self._settings_provider().print_settings

        if (
            print_settings.page_multiple is not None
            and total_pages % print_settings.page_multiple != 0
        ):
            page_multiple = print_settings.page_multiple
            pages_to_add = page_multiple - total_pages % page_multiple

            answer = QMessageBox.warning(
                self,
                self._translator.tr('render.page_multiple_warning_title'),
                self._translator.tr(
                    (
                        "render.page_multiple_warning_one"
                        if pages_to_add == 1
                        else "render.page_multiple_warning_many"
                    ),
                    count=total_pages,
                    multiple=page_multiple,
                    pages_to_add=pages_to_add,
                ),
                (
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
                ),
                QMessageBox.StandardButton.Cancel,
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

        self._pdf_output_edit.setText(str(output_path))

        self._pdf_log_view.clear()
        self._pdf_log_view.setVisible(True)

        self._pdf_progress_bar.setRange(0, total_pages)
        self._pdf_progress_bar.setValue(0)
        self._pdf_progress_bar.setVisible(True)

        self._pdf_log_view.appendPlainText('────────────────────────────────────────')
        self._pdf_log_view.appendPlainText(self._translator.tr('render.log_start'))
        self._pdf_log_view.appendPlainText(str(output_path))
        self._pdf_log_view.appendPlainText(f'{dpi} DPI — {total_pages} pages')
        self._pdf_log_view.appendPlainText('────────────────────────────────────────')

        self.generate_button.setEnabled(False)
        self._pdf_output_button.setEnabled(False)
        self._pdf_dpi_combo.setEnabled(False)

        service = PdfExportService(self._translator)

        thread = QThread(self)

        worker = PdfExportWorker(
            service,
            output_path=output_path,
            result=result,
            settings=settings,
            photos=photos,
            page_width_mm=width_mm,
            page_height_mm=height_mm,
            dpi=dpi,
            metadata=metadata,
            content=export_content,
            prepare_assets=self._project_service.materialize_originals,
            translator=self._translator,
        )

        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.progress.connect(self._pdf_export_progress)

        worker.finished.connect(self._pdf_export_finished)

        worker.failed.connect(self._pdf_export_failed)

        worker.finished.connect(thread.quit)

        worker.failed.connect(thread.quit)

        thread.finished.connect(worker.deleteLater)


        thread.finished.connect(self._pdf_export_thread_finished)

        self._pdf_thread = thread
        self._pdf_worker = worker

        self._pdf_log_view.appendPlainText(self._translator.tr('render.log_engine_start'))

        thread.start()

    def _pdf_export_progress(self, current: int, total: int, message: str) -> None:
        self._pdf_progress_bar.setRange(0, total)
        self._pdf_progress_bar.setValue(current)

        self._pdf_log_view.appendPlainText(f'[{current}/{total}] {message}')

        scrollbar = self._pdf_log_view.verticalScrollBar()

        scrollbar.setValue(scrollbar.maximum())

    def _pdf_export_finished(self, output_path) -> None:
        self._pdf_log_view.appendPlainText('────────────────────────────────────────')
        self._pdf_log_view.appendPlainText(self._translator.tr('render.log_success'))

        self.status_message.emit(
            self._translator.tr('render.generate_success', path=output_path),
            10000,
        )

        QMessageBox.information(
            self,
            self._translator.tr('render.generate_success_title'),
            self._translator.tr('render.generate_success', path=output_path),
        )

    def _pdf_export_failed(self, error: str) -> None:
        self._pdf_log_view.appendPlainText('────────────────────────────────────────')
        self._pdf_log_view.appendPlainText(self._translator.tr('render.log_error', error=error))

        # The worker already turns known failures (notably a missing remote
        # source session) into a user-facing localized message. Surface that
        # message directly instead of hiding the actionable cause behind the
        # generic “Could not generate the PDF” popup.
        self.error.emit(error)

    def _pdf_export_thread_finished(self) -> None:
        thread = self._pdf_thread
        if thread is not None:
            # finished can arrive before native thread cleanup has completed.
            thread.wait()
        self._pdf_worker = None
        self._pdf_thread = None
        if thread is not None:
            thread.deleteLater()

        self.generate_button.setEnabled(True)
        self._pdf_output_button.setEnabled(True)
        self._pdf_dpi_combo.setEnabled(True)
