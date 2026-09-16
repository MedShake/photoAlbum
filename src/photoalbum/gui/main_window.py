from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent
from PySide6.QtCore import QPoint
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame
from PySide6.QtCore import (
    QSortFilterProxyModel,
    QThread,
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QImageReader,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
    QTabWidget,
)

from photoalbum import __version__
from photoalbum.i18n.date_formatter import (
    datetime_edit_format,
    format_datetime,
)
from photoalbum.app import ProjectService
from photoalbum.gui.models import PhotoTableModel
from photoalbum.gui.widgets.photo_actions_delegate import (
    PhotoActionsDelegate,
)
from photoalbum.gui.workers import (
    GpsGeocodingWorker,
    PdfExportWorker,
    ScanWorker,
)
from photoalbum.scanner import (
    LibraryScanResult,
    ProcessingEvent,
)

from photoalbum.album import (
    AlbumBuilder,
    page_format_from_id,
    PrintConstraints,
)
from photoalbum.gui.widgets import (
    AlbumPlanWidget,
    AlbumPreviewWidget,
    AlbumSettingsWidget,
    PhotoPlacesWidget,
)
from photoalbum.gui.preview_render_service import (
    PREVIEW_RENDER_HEIGHT,
    PREVIEW_RENDER_WIDTH,
    PreviewRenderService,
)
from photoalbum.template_engine import (
    create_template_registry,
    register_discovered_template_extensions,
)
from photoalbum.i18n import Translator
from photoalbum.export import (
    PdfExportService,
    PdfMetadata,
)
class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        language: str = "en",
    ) -> None:
        super().__init__()

        self._language = language
        self._project_service = ProjectService()
        self._translator = Translator(
            self._language
        )

        self._preview_render_service = (
            PreviewRenderService(
                self._translator,
                self,
            )
        )

        self._template_registry = (
            create_template_registry()
        )

        register_discovered_template_extensions()
        self._album_build_result = None

        self._album_builder = AlbumBuilder(
            self._template_registry
        )
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None
        self._gps_thread: QThread | None = None
        self._gps_worker: GpsGeocodingWorker | None = None
        self._gps_photo_path: Path | None = None
        self._pdf_thread: QThread | None = None
        self._pdf_worker: PdfExportWorker | None = None
        self._scan_total_files = 0
        self._scan_seen_paths: set[str] = set()
        self._analysis_completed = False

        self.setWindowTitle("Photo Album")
        self.resize(1100, 700)

        self._create_actions()
        self._create_menu()
        self._create_content()
        self._create_status_bar()

        self._update_project_state()

    def closeEvent(self, event) -> None:
        if self._pdf_thread is not None:
            QMessageBox.warning(
                self,
                "Photo Album",
                (
                    "La génération du PDF est en cours. "
                    "Attendez sa fin avant de fermer "
                    "l'application."
                ),
            )
            event.ignore()
            return

        if self._scan_thread is not None:
            QMessageBox.warning(
                self,
                "Photo Album",
                self._translator.tr(
                    "main.scan_running_warning"
                ),
            )
            event.ignore()
            return

        self._project_service.close()
        super().closeEvent(event)

    def _create_actions(self) -> None:
        self._new_project_action = QAction(
            self._translator.tr("main.new_project"),
            self,
        )
        self._new_project_action.triggered.connect(
            self._new_project
        )

        self._open_project_action = QAction(
            self._translator.tr("main.open_project"),
            self,
        )
        self._open_project_action.triggered.connect(
            self._open_project
        )

        self._close_project_action = QAction(
            self._translator.tr("main.close_project"),
            self,
        )
        self._close_project_action.triggered.connect(
            self._close_project
        )

        self._quit_action = QAction(
            self._translator.tr("main.quit"),
            self,
        )
        self._quit_action.triggered.connect(self.close)

        self._about_action = QAction(
            self._translator.tr("main.about"),
            self,
        )
        self._about_action.triggered.connect(
            self._show_about_dialog
        )

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu(self._translator.tr("main.file"))

        file_menu.addAction(self._new_project_action)
        file_menu.addAction(self._open_project_action)
        file_menu.addAction(self._close_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self._quit_action)

        help_menu = self.menuBar().addMenu(
            self._translator.tr("main.help")
        )
        help_menu.addAction(
            self._about_action
        )

    def _show_about_dialog(self) -> None:
        """Display information about Photo Album."""
        dialog = QDialog(self)
        dialog.setWindowTitle(
            self._translator.tr("about.window_title")
        )
        dialog.setMinimumWidth(700)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(
            32,
            24,
            32,
            20,
        )
        layout.setSpacing(14)

        title = QLabel("Photo Album")
        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        title.setStyleSheet(
            "font-size: 26px; font-weight: bold;"
        )
        layout.addWidget(title)

        version_label = QLabel(
            self._translator.tr(
                "about.version",
                version=__version__,
            )
        )
        version_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(version_label)

        slogan = QLabel(
            self._translator.tr("about.slogan")
        )
        slogan.setWordWrap(True)
        slogan.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        slogan.setStyleSheet(
            "font-size: 15px; font-weight: bold;"
        )
        layout.addWidget(slogan)

        # Keep the complete body in one label so Qt can calculate
        # the wrapped height naturally as a single document.
        body = QLabel(
            self._translator.tr("about.description")
            + "<br><br>"
            + self._translator.tr("about.author")
            + "<br><br>"
            + self._translator.tr("about.license")
        )
        body.setTextFormat(
            Qt.TextFormat.RichText
        )
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        body.setOpenExternalLinks(True)
        layout.addWidget(body)

        dedication = QLabel(
            self._translator.tr("about.dedication")
        )
        dedication.setTextFormat(
            Qt.TextFormat.RichText
        )
        dedication.setWordWrap(True)
        dedication.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(dedication)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(
            dialog.reject
        )
        layout.addWidget(buttons)

        dialog.adjustSize()
        dialog.exec()

    def _create_content(self) -> None:
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        self._project_label = QLabel()
        self._project_label.setStyleSheet(
            "font-size: 20px; font-weight: bold;"
        )

        layout.addWidget(self._project_label)

        # ----------------------------------------------------
        # Main project workflow
        # ----------------------------------------------------

        self._tabs = QTabWidget()
        layout.addWidget(
            self._tabs,
            1,
        )

        # ----------------------------------------------------
        # Photos
        # ----------------------------------------------------

        self._photos_sources_tab = QWidget()
        sources_layout = QVBoxLayout(
            self._photos_sources_tab
        )

        # Source folder.
        source_layout = QHBoxLayout()

        self._source_edit = QLineEdit()
        self._source_edit.setReadOnly(
            True
        )

        self._browse_source_button = QPushButton(
            self._translator.tr(
                "main.choose_source"
            )
        )

        self._browse_source_button.clicked.connect(
            self._choose_source_directory
        )

        source_layout.addWidget(
            QLabel(
                self._translator.tr(
                    "main.source_folder"
                )
            )
        )

        source_layout.addWidget(
            self._source_edit,
            1,
        )

        source_layout.addWidget(
            self._browse_source_button
        )

        sources_layout.addLayout(
            source_layout
        )

        # Recursive scan.
        self._recursive_checkbox = QCheckBox(
            self._translator.tr(
                "main.include_subdirectories"
            )
        )

        self._recursive_checkbox.toggled.connect(
            self._recursive_changed
        )

        sources_layout.addWidget(
            self._recursive_checkbox
        )

        # Analysis controls.
        action_layout = QHBoxLayout()

        self._analyze_button = QPushButton(
            self._translator.tr(
                "main.analyze_photos"
            )
        )

        self._analyze_button.clicked.connect(
            self._start_scan
        )

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(
            False
        )

        action_layout.addWidget(
            self._analyze_button
        )

        action_layout.addWidget(
            self._progress_bar,
            1,
        )

        sources_layout.addLayout(
            action_layout
        )

        # Analysis summary.
        self._summary_label = QLabel(
            self._translator.tr(
                "main.no_analysis"
            )
        )

        sources_layout.addWidget(
            self._summary_label
        )

        self._photo_model = PhotoTableModel(
            translator=self._translator,
            parent=self,
        )

        self._photo_proxy_model = QSortFilterProxyModel(self)
        self._photo_proxy_model.setSourceModel(
            self._photo_model
        )
        self._photo_proxy_model.setSortRole(
            PhotoTableModel.SORT_ROLE
        )
        self._photo_proxy_model.setSortCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self._photo_proxy_model.setDynamicSortFilter(True)

        self._photo_table = QTableView()
        self._photo_table.setModel(
            self._photo_proxy_model
        )

        self._source_preview = None
        self._source_preview_row = None
        self._source_preview_position = QPoint()

        self._source_preview_timer = QTimer(self)
        self._source_preview_timer.setSingleShot(True)
        self._source_preview_timer.setInterval(350)
        self._source_preview_timer.timeout.connect(
            self._show_pending_source_photo_preview
        )

        self._photo_table.setMouseTracking(True)
        self._photo_table.viewport().installEventFilter(self)

        self._photo_actions_delegate = (
            PhotoActionsDelegate(
                self._photo_table
            )
        )

        self._photo_actions_delegate.edit_datetime_requested.connect(
            self._edit_photo_datetime
        )
        self._photo_actions_delegate.edit_gps_requested.connect(
            self._edit_photo_gps
        )
        self._photo_actions_delegate.open_photo_requested.connect(
            self._open_photo_in_os
        )

        self._photo_table.setItemDelegateForColumn(
            1,
            self._photo_actions_delegate,
        )

        self._photo_table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )
        self._photo_table.setSelectionMode(
            QTableView.SelectionMode.SingleSelection
        )
        self._photo_table.setAlternatingRowColors(True)
        self._photo_table.setSortingEnabled(True)

        self._photo_table.sortByColumn(
            2,
            Qt.SortOrder.AscendingOrder,
        )

        header = self._photo_table.horizontalHeader()

        # Let the user resize columns manually.
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        # Sensible initial widths. Long filenames must not force
        # the complete table to become excessively wide.
        self._photo_table.setColumnWidth(0, 260)
        self._photo_table.setColumnWidth(1, 116)
        self._photo_table.setColumnWidth(2, 170)
        self._photo_table.setColumnWidth(3, 130)
        self._photo_table.setColumnWidth(4, 70)
        self._photo_table.setColumnWidth(5, 150)
        self._photo_table.setColumnWidth(6, 160)
        self._photo_table.setColumnWidth(7, 120)

        header.setStretchLastSection(False)

        # Keep the sorted section visually consistent with the
        # other column headers.
        header_font = header.font()
        header_font.setBold(False)
        header.setFont(header_font)
        header.setStyleSheet(
            "QHeaderView::section { font-weight: normal; }"
        )

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)

        splitter = QSplitter(
            Qt.Orientation.Vertical
        )

        splitter.addWidget(self._photo_table)
        splitter.addWidget(self._log_view)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        sources_layout.addWidget(
            QLabel(self._translator.tr("main.photos"))
        )
        sources_layout.addWidget(splitter, 1)

        self._tabs.addTab(
            self._photos_sources_tab,
            self._translator.tr("tab.photos"),
        )

        # ----------------------------------------------------
        # Lieux et légendes
        # ----------------------------------------------------

        self._photos_places_widget = PhotoPlacesWidget(
            translator=self._translator,
            save_location=self._save_photo_editorial_location,
            save_caption=self._save_photo_caption,
            edit_source_photo=self._go_to_source_photo,
            parent=self,
        )

        self._photos_places_index = (
            self._tabs.addTab(
                self._photos_places_widget,
                self._translator.tr(
                    "tab.places_captions"
                ),
            )
        )

        self._album_settings_widget = AlbumSettingsWidget(
            self._template_registry,
            translator=self._translator,
            parent=self,
            render_service=self._preview_render_service,
        )

        self._album_settings_widget.set_photo_provider(
            self._project_service.list_photos
        )

        self._album_settings_widget.settings_changed.connect(
            self._save_album_settings
        )

        self._tabs.addTab(
            self._album_settings_widget,
            self._translator.tr("tab.album"),
        )

        self._album_plan_widget = AlbumPlanWidget(
            self._template_registry,
            translator=self._translator,
            parent=self,
        )

        self._album_preview_widget = AlbumPreviewWidget(
            self._template_registry,
            translator=self._translator,
            parent=self,
            render_service=self._preview_render_service,

        )

        self._tabs.addTab(
            self._album_plan_widget,
            self._translator.tr("tab.plan"),
        )

        self._tabs.addTab(
            self._album_preview_widget,
            self._translator.tr("tab.preview"),
        )

        # ----------------------------------------------------
        # Final rendering / PDF tab
        # ----------------------------------------------------

        self._render_tab = QWidget()

        render_layout = QVBoxLayout(
            self._render_tab
        )

        render_title = QLabel(
            self._translator.tr(
                "render.title"
            )
        )
        render_title.setStyleSheet(
            "font-size: 18px; font-weight: bold;"
        )
        render_layout.addWidget(render_title)

        render_description = QLabel(
            self._translator.tr(
                "render.description"
            )
        )
        render_description.setWordWrap(True)
        render_layout.addWidget(
            render_description
        )

        # Output file.
        output_group = QGroupBox(
            self._translator.tr(
                "render.output_group"
            )
        )
        output_layout = QHBoxLayout(
            output_group
        )

        self._pdf_output_edit = QLineEdit()
        self._pdf_output_edit.setPlaceholderText(
            self._translator.tr(
                "render.output_placeholder"
            )
        )

        self._pdf_output_button = QPushButton(
            self._translator.tr(
                "render.browse"
            )
        )
        self._pdf_output_button.clicked.connect(
            self._choose_pdf_output
        )

        output_layout.addWidget(
            self._pdf_output_edit,
            1,
        )
        output_layout.addWidget(
            self._pdf_output_button
        )

        render_layout.addWidget(output_group)

        # Quality.
        quality_group = QGroupBox(
            self._translator.tr(
                "render.quality_group"
            )
        )
        quality_layout = QFormLayout(
            quality_group
        )

        self._pdf_dpi_combo = QComboBox()

        self._pdf_dpi_combo.addItem(
            self._translator.tr(
                "render.dpi_screen"
            ),
            96,
        )
        self._pdf_dpi_combo.addItem(
            self._translator.tr(
                "render.dpi_good"
            ),
            150,
        )
        self._pdf_dpi_combo.addItem(
            self._translator.tr(
                "render.dpi_print"
            ),
            300,
        )
        self._pdf_dpi_combo.addItem(
            self._translator.tr(
                "render.dpi_high"
            ),
            600,
        )

        self._pdf_dpi_combo.setCurrentIndex(2)
        self._pdf_dpi_combo.currentIndexChanged.connect(
            self._update_pdf_summary
        )

        quality_layout.addRow(
            self._translator.tr(
                "render.resolution"
            ),
            self._pdf_dpi_combo,
        )

        self._pdf_pixel_size_label = QLabel()
        self._pdf_pixel_size_label.setWordWrap(True)

        quality_layout.addRow(
            self._translator.tr(
                "render.pixel_size"
            ),
            self._pdf_pixel_size_label,
        )

        render_layout.addWidget(quality_group)

        # PDF metadata.
        metadata_group = QGroupBox(
            self._translator.tr(
                "render.metadata_group"
            )
        )
        metadata_layout = QFormLayout(
            metadata_group
        )

        self._pdf_title_edit = QLineEdit()
        self._pdf_author_edit = QLineEdit()
        self._pdf_subject_edit = QLineEdit()
        self._pdf_keywords_edit = QLineEdit()

        metadata_layout.addRow(
            self._translator.tr(
                "render.metadata_title"
            ),
            self._pdf_title_edit,
        )
        metadata_layout.addRow(
            self._translator.tr(
                "render.metadata_author"
            ),
            self._pdf_author_edit,
        )
        metadata_layout.addRow(
            self._translator.tr(
                "render.metadata_subject"
            ),
            self._pdf_subject_edit,
        )
        metadata_layout.addRow(
            self._translator.tr(
                "render.metadata_keywords"
            ),
            self._pdf_keywords_edit,
        )

        render_layout.addWidget(metadata_group)

        # Document summary.
        document_group = QGroupBox(
            self._translator.tr(
                "render.document_group"
            )
        )
        document_layout = QFormLayout(
            document_group
        )

        self._pdf_format_label = QLabel()
        self._pdf_orientation_label = QLabel()
        self._pdf_pages_label = QLabel()
        self._pdf_photos_label = QLabel()

        document_layout.addRow(
            self._translator.tr(
                "render.document_format"
            ),
            self._pdf_format_label,
        )
        document_layout.addRow(
            self._translator.tr(
                "render.document_orientation"
            ),
            self._pdf_orientation_label,
        )
        document_layout.addRow(
            self._translator.tr(
                "render.document_pages"
            ),
            self._pdf_pages_label,
        )
        document_layout.addRow(
            self._translator.tr(
                "render.document_photos"
            ),
            self._pdf_photos_label,
        )

        render_layout.addWidget(document_group)

        self._pdf_progress_bar = QProgressBar()
        self._pdf_progress_bar.setRange(
            0,
            1,
        )
        self._pdf_progress_bar.setValue(0)
        self._pdf_progress_bar.setFormat(
            "%v / %m pages — %p%"
        )
        self._pdf_progress_bar.setVisible(
            False
        )

        render_layout.addWidget(
            self._pdf_progress_bar
        )

        self._pdf_log_view = QPlainTextEdit()
        self._pdf_log_view.setReadOnly(True)
        self._pdf_log_view.setMaximumBlockCount(
            2000
        )
        self._pdf_log_view.setVisible(
            False
        )

        self._pdf_log_view.setMaximumHeight(280)

        render_layout.addWidget(
            self._pdf_log_view
        )

        render_layout.addStretch(1)

        action_layout = QHBoxLayout()
        action_layout.addStretch(1)

        self._generate_pdf_button = QPushButton(
            self._translator.tr(
                "render.generate"
            )
        )

        self._generate_pdf_button.clicked.connect(
            self._generate_pdf
        )

        action_layout.addWidget(
            self._generate_pdf_button
        )

        render_layout.addLayout(action_layout)

        self._tabs.addTab(
            self._render_tab,
            self._translator.tr(
                "tab.render"
            ),
        )

        self._update_pdf_summary()

        self.setCentralWidget(central_widget)

    def _choose_pdf_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._translator.tr(
                "render.output_dialog"
            ),
            self._pdf_output_edit.text(),
            "PDF (*.pdf)",
        )

        if not path:
            return

        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        self._pdf_output_edit.setText(path)

    def _update_pdf_summary(self) -> None:
        if not hasattr(
            self,
            "_pdf_format_label",
        ):
            return

        try:
            settings = (
                self._album_settings_widget.settings()
            )
        except Exception:
            return

        page_format = page_format_from_id(
            settings.page_format
        )

        format_name = page_format.name
        width_mm = page_format.width_mm
        height_mm = page_format.height_mm

        orientation = (
            settings.orientation.value
        )

        if orientation == "landscape":
            width_mm, height_mm = (
                height_mm,
                width_mm,
            )

        dpi = int(
            self._pdf_dpi_combo.currentData()
        )

        width_px = round(
            width_mm / 25.4 * dpi
        )
        height_px = round(
            height_mm / 25.4 * dpi
        )

        self._pdf_format_label.setText(
            (
                f"{format_name} — "
                f"{width_mm:g} × "
                f"{height_mm:g} mm"
            )
        )

        if orientation == "landscape":
            orientation_text = (
                self._translator.tr(
                    "render.landscape"
                )
            )
        else:
            orientation_text = (
                self._translator.tr(
                    "render.portrait"
                )
            )

        self._pdf_orientation_label.setText(
            orientation_text
        )

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
            photos = (
                self._project_service.list_photos()
            )

        self._pdf_photos_label.setText(
            str(len(photos))
        )

        result = self._album_build_result

        if result is None:
            self._pdf_pages_label.setText(
                self._translator.tr(
                    "render.page_count_pending"
                )
            )
        else:
            self._pdf_pages_label.setText(
                str(
                    result.total_page_count
                )
            )

    def _generate_pdf(self) -> None:
        if self._pdf_thread is not None:
            return

        if not self._project_service.is_open:
            self._show_error(
                self._translator.tr(
                    "main.no_project_error"
                )
            )
            return

        result = self._album_build_result

        if result is None:
            self._show_error(
                self._translator.tr(
                    "render.no_album"
                )
            )
            return

        output_text = (
            self._pdf_output_edit.text().strip()
        )

        if not output_text:
            self._show_error(
                self._translator.tr(
                    "render.output_required"
                )
            )
            return

        output_path = Path(
            output_text
        )

        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(
                ".pdf"
            )

        try:
            settings = (
                self._album_settings_widget.settings()
            )

            page_format = page_format_from_id(
                settings.page_format
            )

            width_mm = page_format.width_mm
            height_mm = page_format.height_mm

            if (
                settings.orientation.value
                == "landscape"
            ):
                width_mm, height_mm = (
                    height_mm,
                    width_mm,
                )

            dpi = int(
                self._pdf_dpi_combo.currentData()
            )

            photos = (
                self._project_service.list_photos()
            )

            metadata = PdfMetadata(
                title=(
                    self._pdf_title_edit
                    .text()
                    .strip()
                ),
                author=(
                    self._pdf_author_edit
                    .text()
                    .strip()
                ),
                subject=(
                    self._pdf_subject_edit
                    .text()
                    .strip()
                ),
                keywords=(
                    self._pdf_keywords_edit
                    .text()
                    .strip()
                ),
            )

        except Exception as exc:
            self._show_error(
                self._translator.tr(
                    "render.generate_error",
                    error=exc,
                )
            )
            return

        total_pages = (
            len(result.pagination.pages)
            + 4
        )

        self._pdf_output_edit.setText(
            str(output_path)
        )

        self._pdf_log_view.clear()
        self._pdf_log_view.setVisible(True)

        self._pdf_progress_bar.setRange(
            0,
            total_pages,
        )
        self._pdf_progress_bar.setValue(0)
        self._pdf_progress_bar.setVisible(
            True
        )

        self._pdf_log_view.appendPlainText(
            "────────────────────────────────────────"
        )
        self._pdf_log_view.appendPlainText(
            "Génération du PDF"
        )
        self._pdf_log_view.appendPlainText(
            str(output_path)
        )
        self._pdf_log_view.appendPlainText(
            f"{dpi} DPI — {total_pages} pages"
        )
        self._pdf_log_view.appendPlainText(
            "────────────────────────────────────────"
        )

        self._generate_pdf_button.setEnabled(
            False
        )
        self._pdf_output_button.setEnabled(
            False
        )
        self._pdf_dpi_combo.setEnabled(
            False
        )

        service = PdfExportService(
            self._translator
        )

        thread = QThread(
            self
        )

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
        )

        worker.moveToThread(
            thread
        )

        thread.started.connect(
            worker.run
        )

        worker.progress.connect(
            self._pdf_export_progress
        )

        worker.finished.connect(
            self._pdf_export_finished
        )

        worker.failed.connect(
            self._pdf_export_failed
        )

        worker.finished.connect(
            thread.quit
        )

        worker.failed.connect(
            thread.quit
        )

        thread.finished.connect(
            worker.deleteLater
        )

        thread.finished.connect(
            thread.deleteLater
        )

        thread.finished.connect(
            self._pdf_export_thread_finished
        )

        self._pdf_thread = thread
        self._pdf_worker = worker

        self._pdf_log_view.appendPlainText(
            "Démarrage du moteur de rendu…"
        )

        thread.start()

    def _pdf_export_progress(
        self,
        current: int,
        total: int,
        message: str,
    ) -> None:
        self._pdf_progress_bar.setRange(
            0,
            total,
        )
        self._pdf_progress_bar.setValue(
            current
        )

        self._pdf_log_view.appendPlainText(
            f"[{current}/{total}] {message}"
        )

        scrollbar = (
            self._pdf_log_view.verticalScrollBar()
        )

        scrollbar.setValue(
            scrollbar.maximum()
        )

    def _pdf_export_finished(
        self,
        output_path,
    ) -> None:
        self._pdf_log_view.appendPlainText(
            "────────────────────────────────────────"
        )
        self._pdf_log_view.appendPlainText(
            "PDF créé avec succès."
        )

        self.statusBar().showMessage(
            self._translator.tr(
                "render.generate_success",
                path=output_path,
            ),
            10000,
        )

        QMessageBox.information(
            self,
            self._translator.tr(
                "render.generate_success_title"
            ),
            self._translator.tr(
                "render.generate_success",
                path=output_path,
            ),
        )

    def _pdf_export_failed(
        self,
        error: str,
    ) -> None:
        self._pdf_log_view.appendPlainText(
            "────────────────────────────────────────"
        )
        self._pdf_log_view.appendPlainText(
            f"ERREUR : {error}"
        )

        self._show_error(
            self._translator.tr(
                "render.generate_error",
                error=error,
            )
        )

    def _pdf_export_thread_finished(
        self,
    ) -> None:
        self._pdf_thread = None
        self._pdf_worker = None

        self._generate_pdf_button.setEnabled(
            True
        )
        self._pdf_output_button.setEnabled(
            True
        )
        self._pdf_dpi_combo.setEnabled(
            True
        )

    def _create_status_bar(self) -> None:
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

    def _new_project(self) -> None:
        self._preview_render_service.clear()
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._translator.tr(
                "main.new_project"
            ),
            "",
            "Photo Album Project (*.photoalbum)",
        )

        if not path:
            return

        project_path = Path(path)

        if project_path.suffix != ".photoalbum":
            project_path = (
                project_path.with_suffix(
                    ".photoalbum"
                )
            )

        try:
            # QFileDialog already asked the user whether the
            # existing file may be replaced. Honour that choice.
            if self._project_service.is_open:
                self._project_service.close()

            if project_path.exists():
                project_path.unlink()

            self._project_service.create(
                project_path
            )

        except Exception as exc:
            self._show_error(
                str(exc)
            )
            return

        self._analysis_completed = False

        self._source_edit.clear()

        previous = (
            self._recursive_checkbox.blockSignals(
                True
            )
        )

        self._recursive_checkbox.setChecked(
            False
        )

        self._recursive_checkbox.blockSignals(
            previous
        )

        self._summary_label.setText(
            self._translator.tr(
                "main.no_analysis"
            )
        )

        self._log_view.clear()
        self._photo_model.clear()

        self._album_settings_widget.reset_to_defaults()
        self._album_settings_widget.set_available_years(
            set()
        )

        self._album_plan_widget.clear()
        self._album_preview_widget.clear()

        self._load_project_settings()
        self._load_project_photos()
        self._update_project_state()

    def _open_project(self) -> None:
        self._preview_render_service.clear()
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._translator.tr("main.open_project_title"),
            "",
            "Photo Album Project (*.photoalbum)",
        )

        if not path:
            return

        try:
            self._project_service.open(Path(path))
        except Exception as exc:
            self._show_error(str(exc))
            return

        self._load_project_settings()
        self._load_project_photos()
        self._update_project_state()

        # Opening an existing project also synchronizes it with
        # its source directory. The scanner already reuses
        # unchanged photos, so only new or changed files require
        # actual analysis.
        if self._source_edit.text().strip():
            self._start_scan()

    def _close_project(self) -> None:
        self._preview_render_service.clear()
        self._album_build_result = None
        self._project_service.close()

        self._analysis_completed = False
        self._scan_total_files = 0
        self._scan_seen_paths.clear()

        self._album_plan_widget.clear()
        self._album_preview_widget.clear()

        self._source_edit.clear()
        self._recursive_checkbox.setChecked(False)
        self._summary_label.setText(
            self._translator.tr("main.no_analysis")
        )
        self._log_view.clear()
        self._photo_model.clear()
        self._photos_places_widget.clear()
        self._album_settings_widget.set_available_years(
            set()
        )
        self._album_settings_widget.reset_to_defaults()
        self._album_plan_widget.clear()
        self._update_project_state()

    def _choose_source_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            self._translator.tr(
                "main.choose_source"
            ),
        )

        if not directory:
            return

        try:
            self._project_service.set_source_directory(
                Path(directory)
            )
        except Exception as exc:
            self._show_error(
                str(exc)
            )
            return

        self._source_edit.setText(
            directory
        )

        self._analysis_completed = False

        self._update_project_state()

        # Choosing a source folder defines the photo library:
        # analysis therefore starts immediately.
        self._start_scan()

    def _recursive_changed(
        self,
        checked: bool,
    ) -> None:
        if not self._project_service.is_open:
            return

        self._project_service.set_recursive_scan(
            checked
        )

        source_directory = (
            self._project_service.get_source_directory()
        )

        if (
            source_directory is not None
            and self._scan_thread is None
        ):
            self._analysis_completed = False
            self._start_scan()

    def _load_project_settings(self) -> None:
        source_directory = (
            self._project_service.get_source_directory()
        )

        self._source_edit.setText(
            str(source_directory)
            if source_directory is not None
            else ""
        )

        self._recursive_checkbox.setChecked(
            self._project_service.get_recursive_scan()
        )
        
        album_settings = (
            self._project_service.get_album_structure_settings()
        )

        if album_settings is None:
            self._album_settings_widget.reset_to_defaults()
        else:
            self._album_settings_widget.set_settings(
                album_settings
            )

    def _start_scan(self) -> None:
        if self._scan_thread is not None:
            return

        project_path = self._project_service.project_path
        source_directory = (
            self._project_service.get_source_directory()
        )

        if project_path is None:
            self._show_error(
                self._translator.tr("main.no_project_error")
            )
            return

        if source_directory is None:
            self._show_error(
                self._translator.tr(
                    "main.choose_source_error"
                )
            )
            return

        if not source_directory.exists():
            message = self._translator.tr(
                "main.source_missing_error",
                path=source_directory,
            )

            if self._log_view.document().blockCount() > 1:
                self._log_view.appendPlainText(
                    ""
                )

            self._log_view.appendPlainText(
                "────────────────────────────────────────"
            )
            self._log_view.appendPlainText(
                f"⚠ {message}"
            )
            self._log_view.appendPlainText(
                "────────────────────────────────────────"
            )

            self._summary_label.setText(
                message
            )

            self._show_error(
                message
            )

            # The source folder is unavailable: Photos is the
            # only meaningful tab until the source is fixed.
            self._set_scan_running(
                False
            )

            self._tabs.setCurrentIndex(
                0
            )

            return

        # Keep the analysis log for the whole project session.
        # A new scan starts a new section instead of erasing
        # previous events.
        if self._log_view.document().blockCount() > 1:
            self._log_view.appendPlainText(
                ""
            )

        self._log_view.appendPlainText(
            "────────────────────────────────────────"
        )
        self._log_view.appendPlainText(
            self._translator.tr(
                "main.analysis_log_header",
                path=source_directory,
            )
        )
        self._log_view.appendPlainText(
            "────────────────────────────────────────"
        )

        self._summary_label.setText(
            self._translator.tr("main.analysis_running")
        )

        self._set_scan_running(True)

        thread = QThread(self)

        worker = ScanWorker(
            project_path=project_path,
            source_directory=source_directory,
            recursive=(
                self._project_service.get_recursive_scan()
            ),
            language=self._language,
            geocode=True,
            user_agent="PhotoAlbum/0.1 development",
        )

        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.event_received.connect(
            self._handle_processing_event
        )
        worker.completed.connect(
            self._scan_completed
        )
        worker.failed.connect(
            self._scan_failed
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

    def _update_scan_progress(
        self,
        current: int,
    ) -> None:
        total = self._scan_total_files

        if total <= 0:
            self._progress_bar.setRange(
                0,
                0,
            )
            self._progress_bar.setFormat(
                self._translator.tr(
                    "main.analysis_in_progress"
                )
            )
            return

        current = min(
            max(current, 0),
            total,
        )

        self._progress_bar.setRange(
            0,
            total,
        )

        self._progress_bar.setValue(
            current
        )

        self._progress_bar.setFormat(
            self._translator.tr(
                "main.progress_photos",
                current=current,
                total=total,
            )
        )

        self._summary_label.setText(
            self._translator.tr(
                "main.analysis_progress",
                current=current,
                total=total,
                remaining=max(
                    total - current,
                    0,
                ),
            )
        )

    def _handle_processing_event(
        self,
        event: ProcessingEvent,
    ) -> None:
        path_key = str(
            event.path
        )

        # Several events may concern the same photo
        # (EXIF, GPS, geocoding...). Count the photo once.
        if (
            path_key
            and path_key
            not in self._scan_seen_paths
        ):
            self._scan_seen_paths.add(
                path_key
            )

            self._update_scan_progress(
                len(
                    self._scan_seen_paths
                )
            )

        message = (
            self._translated_processing_event(
                event
            )
            if hasattr(
                self,
                "_translated_processing_event"
            )
            else event.message
        )

        self._log_view.appendPlainText(
            f"[{event.type.value}] "
            f"{event.path.name} : "
            f"{message}"
        )

    def _scan_completed(
        self,
        result: LibraryScanResult,
    ) -> None:
        statistics = result.statistics

        self._update_scan_progress(
            self._scan_total_files
        )
        self._analysis_completed = True

        all_photos = [
            *result.photos,
            *result.date_anomalies,
        ]

        all_photos.sort(
            key=lambda photo: (
                photo.capture_datetime is None,
                photo.capture_datetime
                or datetime.max,
                photo.filename.lower(),
            )
        )

        self._photo_model.set_photos(all_photos)
        self._photos_places_widget.set_photos(all_photos)
        self._update_album_years(all_photos)
        self._refresh_album_plan()

        if result.missing_photos:
            self._log_view.appendPlainText(
                ""
            )

            self._log_view.appendPlainText(
                self._translator.tr(
                    "main.missing_photos_log_header",
                    count=len(
                        result.missing_photos
                    ),
                )
            )

            for photo in result.missing_photos:
                self._log_view.appendPlainText(
                    self._translator.tr(
                        "main.missing_photo_log",
                        path=photo.path,
                    )
                )

            QMessageBox.warning(
                self,
                self._translator.tr(
                    "main.missing_photos_title"
                ),
                self._translator.tr(
                    "main.missing_photos_warning",
                    count=len(
                        result.missing_photos
                    ),
                ),
            )

        self._summary_label.setText(
            " | ".join(
                [
                    self._translator.tr(
                        "main.discovered",
                        count=statistics.discovered,
                    ),
                    self._translator.tr(
                        "main.analyzed",
                        count=statistics.analyzed,
                    ),
                    self._translator.tr(
                        "main.reused",
                        count=statistics.reused,
                    ),
                    self._translator.tr(
                        "main.geocoded",
                        count=statistics.geocoded,
                    ),
                    self._translator.tr(
                        "main.date_anomalies",
                        count=statistics.date_anomalies,
                    ),
                    self._translator.tr(
                        "main.errors",
                        count=statistics.errors,
                    ),
                ]
            )
        )

        if result.date_anomalies:
            self._log_view.appendPlainText("")
            self._log_view.appendPlainText(
                self._translator.tr(
                    "main.photos_requiring_date"
                )
            )

            for photo in result.date_anomalies:
                self._log_view.appendPlainText(
                    str(photo.path)
                )

        self.statusBar().showMessage(
            self._translator.tr("main.analysis_completed")
        )

    def _scan_failed(
        self,
        message: str,
    ) -> None:
        self._summary_label.setText(
            self._translator.tr("main.analysis_failed")
        )

        self._show_error(message)

    def _scan_thread_finished(self) -> None:
        self._scan_thread = None
        self._scan_worker = None

        self._set_scan_running(
            False
        )

        if (
            self._project_service.is_open
            and bool(self._source_edit.text())
        ):
            self._analyze_button.setText(
                self._translator.tr(
                    "main.analyze_again"
                )
            )

    def _set_scan_running(
        self,
        running: bool,
    ) -> None:
        self._new_project_action.setEnabled(
            not running
        )

        self._open_project_action.setEnabled(
            not running
        )

        self._close_project_action.setEnabled(
            (
                not running
                and self._project_service.is_open
            )
        )

        self._browse_source_button.setEnabled(
            (
                not running
                and self._project_service.is_open
            )
        )

        self._recursive_checkbox.setEnabled(
            (
                not running
                and self._project_service.is_open
            )
        )

        self._analyze_button.setEnabled(
            (
                not running
                and self._project_service.is_open
                and bool(
                    self._source_edit.text()
                )
            )
        )

        # Photos remains available for source selection,
        # progress and logs.
        #
        # Every derived view requires a valid source folder.
        source_directory = (
            self._project_service.get_source_directory()
            if self._project_service.is_open
            else None
        )

        source_available = (
            source_directory is not None
            and source_directory.exists()
        )

        derived_tabs_enabled = (
            self._project_service.is_open
            and not running
            and source_available
        )

        # Photos remains the project entry point. Every other
        # workflow tab is available as soon as the project contains
        # photos and no scan is currently running.
        photos_available = (
            self._project_service.is_open
            and not running
            and bool(
                self._project_service.list_photos()
            )
        )

        # Photos is always available. It is the entry point
        # for creating/opening a project, selecting the source
        # folder and reading the analysis log.
        if self._tabs.count() > 0:
            self._tabs.setTabEnabled(
                0,
                True,
            )

        for index in range(
            1,
            self._tabs.count(),
        ):
            self._tabs.setTabEnabled(
                index,
                photos_available,
            )

        self._progress_bar.setVisible(
            running
        )

        if running:
            self._analyze_button.setText(
                self._translator.tr(
                    "main.analysis_running_button"
                )
            )

            self.statusBar().showMessage(
                self._translator.tr(
                    "main.analysis_in_progress"
                )
            )

        else:
            if self._analysis_completed:
                self._analyze_button.setText(
                    self._translator.tr(
                        "main.analyze_again"
                    )
                )
            else:
                self._analyze_button.setText(
                    self._translator.tr(
                        "main.analyze_photos"
                    )
                )

    def _update_project_state(self) -> None:
        is_open = self._project_service.is_open
        has_source = bool(self._source_edit.text())

        self._close_project_action.setEnabled(is_open)
        self._browse_source_button.setEnabled(is_open)
        self._recursive_checkbox.setEnabled(is_open)
        self._analyze_button.setEnabled(
            is_open and has_source
        )

        if is_open:
            project_path = self._project_service.project_path

            self._project_label.setText(
                self._translator.tr(
                    "main.project",
                    name=project_path.name,
                )
            )

            self.statusBar().showMessage(
                str(project_path)
            )
        else:
            self._project_label.setText(
                self._translator.tr("main.no_project")
            )
            self.statusBar().showMessage(self._translator.tr("main.ready"))

        # Re-evaluate tab availability as part of every
        # project-state refresh.
        self._set_scan_running(
            self._scan_thread is not None
        )


    def _update_album_years(
        self,
        photos,
    ) -> None:
        years = {
            photo.capture_datetime.year
            for photo in photos
            if photo.capture_datetime is not None
        }

        self._album_settings_widget.set_available_years(
            years
        )

    def _prewarm_expensive_previews(
        self,
        result,
        settings,
        photos,
    ) -> None:
        """
        Pre-render expensive templates using exactly the same
        photo set as the album preview.

        Do NOT use the raw repository photo list here: the album
        plan may exclude undated/anomalous photos or otherwise
        expose a different ordering.
        """

        project_photos = []
        seen_paths = set()

        for item in result.plan.items:
            for photo in item.photos:
                key = str(
                    photo.path
                )

                if key in seen_paths:
                    continue

                seen_paths.add(
                    key
                )

                project_photos.append(
                    photo
                )

        instances = []

        # Covers.
        for cover in settings.covers.values():
            page = cover.page

            if (
                self._preview_render_service.supports(
                    page.template_id
                )
            ):
                instances.append(
                    page
                )

        # Special-page instances.
        for page in (
            list(settings.front_matter)
            + list(settings.back_matter)
        ):
            if (
                self._preview_render_service.supports(
                    page.template_id
                )
            ):
                instances.append(
                    page
                )

        seen_instances = set()

        for instance in instances:
            if (
                instance.instance_id
                in seen_instances
            ):
                continue

            seen_instances.add(
                instance.instance_id
            )

            self._preview_render_service.request(
                instance,
                project_photos,
                width=PREVIEW_RENDER_WIDTH,
                height=PREVIEW_RENDER_HEIGHT,
            )


    def _refresh_album_plan(self) -> None:
        if not self._project_service.is_open:
            self._album_plan_widget.clear()
            self._album_preview_widget.clear()
            return

        try:
            photos = self._project_service.list_photos()

            settings = (
                self._album_settings_widget.settings()
            )

            print_constraints = None

            if settings.print_settings.page_multiple is not None:
                print_constraints = PrintConstraints(
                    page_multiple=(
                        settings.print_settings.page_multiple
                    )
                )

            result = self._album_builder.build(
                photos,
                settings,
                print_constraints=print_constraints,
            )

            self._album_build_result = result

            # Expensive previews are prepared immediately in
            # background so they are usually ready when the
            # Preview tab is opened.

            self._album_plan_widget.set_result(
                result,
                settings,
            )

            page_format = page_format_from_id(
                settings.page_format
            )

            self._album_preview_widget.set_result(
                result,
                settings,
                page_format=page_format,
            )

            # Preview prewarming is strictly optional.
            #
            # It must never prevent Plan or Preview from being
            # displayed if the optimization itself fails.
            try:
                self._prewarm_expensive_previews(
                    result,
                    settings,
                    photos,
                )
            except Exception:
                pass

        except Exception as exc:
            self._album_plan_widget.clear()
            self._album_preview_widget.clear()

            self.statusBar().showMessage(
                self._translator.tr(
                    "main.build_plan_error",
                    error=exc,
                )
            )

    def _save_album_settings(self) -> None:
        if not self._project_service.is_open:
            return

        try:
            settings = self._album_settings_widget.settings()

            self._project_service.set_album_structure_settings(
                settings
            )
            self._refresh_album_plan()
            self._update_pdf_summary()
        except Exception as exc:
            self._show_error(
                self._translator.tr(
                    "main.save_album_error",
                    error=exc,
                )
            )

    def _edit_photo_datetime(
        self,
        photo,
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(
            self._translator.tr(
                "photos.datetime.title"
            )
        )

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        filename_label = QLabel(photo.filename)
        filename_label.setWordWrap(True)

        date_time_edit = QDateTimeEdit(dialog)
        date_time_edit.setCalendarPopup(True)
        date_time_edit.setDisplayFormat(
            datetime_edit_format()
        )
        date_time_edit.setDateTime(
            photo.capture_datetime
            or datetime.now()
        )

        form.addRow(
            self._translator.tr(
                "photos.datetime.photo"
            ),
            filename_label,
        )
        form.addRow(
            self._translator.tr(
                "photos.datetime.value"
            ),
            date_time_edit,
        )

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )

        restore_button = buttons.addButton(
            self._translator.tr(
                "photos.datetime.restore"
            ),
            QDialogButtonBox.ButtonRole.ResetRole,
        )

        original_datetime = (
            photo.original_capture_datetime
        )

        restore_button.setEnabled(
            original_datetime is not None
            and photo.capture_datetime
            != original_datetime
        )

        save_button = buttons.button(
            QDialogButtonBox.StandardButton.Save
        )
        cancel_button = buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        )

        if save_button is not None:
            save_button.setText(
                self._translator.tr(
                    "photos.datetime.save"
                )
            )

        if cancel_button is not None:
            cancel_button.setText(
                self._translator.tr(
                    "photos.datetime.cancel"
                )
            )

        restore_requested = False

        def restore_original_datetime() -> None:
            nonlocal restore_requested
            restore_requested = True
            dialog.accept()

        restore_button.clicked.connect(
            restore_original_datetime
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(buttons)

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        old_datetime = photo.capture_datetime

        if restore_requested:
            if original_datetime is None:
                return

            try:
                self._project_service.\
                    restore_original_capture_datetime(
                        photo.path
                    )
            except Exception as exc:
                self._show_error(str(exc))
                return

            old_date_text = (
                format_datetime(
                    old_datetime,
                    include_seconds=True,
                )
                if old_datetime is not None
                else self._translator.tr(
                    "photos.datetime.no_date"
                )
            )

            self._log_view.appendPlainText(
                self._translator.tr(
                    "photos.datetime.log_restored",
                    filename=photo.filename,
                    old_date=old_date_text,
                    original_date=(
                        format_datetime(
                            original_datetime,
                            include_seconds=True,
                        )
                    ),
                )
            )

            self._load_project_photos()
            return
        new_datetime = (
            date_time_edit.dateTime().toPython()
        )

        try:
            self._project_service.set_manual_capture_datetime(
                photo.path,
                new_datetime,
            )
        except Exception as exc:
            self._show_error(str(exc))
            return

        new_date_text = format_datetime(
            new_datetime,
            include_seconds=True,
        )

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
                old_date=format_datetime(
                    old_datetime,
                    include_seconds=True,
                ),
                new_date=new_date_text,
            )

        self._log_view.appendPlainText(
            log_message
        )

        self._load_project_photos()

    def _edit_photo_gps(
        self,
        photo,
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(
            self._translator.tr(
                "photos.gps.title"
            )
        )

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

        form.addRow(
            self._translator.tr(
                "photos.gps.photo"
            ),
            filename_label,
        )
        form.addRow(
            self._translator.tr(
                "photos.gps.latitude"
            ),
            latitude_edit,
        )
        form.addRow(
            self._translator.tr(
                "photos.gps.longitude"
            ),
            longitude_edit,
        )

        layout.addLayout(form)

        restore_button = QPushButton(
            self._translator.tr(
                "photos.gps.restore"
            ),
            dialog,
        )

        has_original_gps = (
            photo.original_latitude is not None
            and photo.original_longitude is not None
        )

        restore_button.setEnabled(
            has_original_gps
        )

        if has_original_gps:
            layout.addWidget(restore_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )

        save_button = buttons.button(
            QDialogButtonBox.StandardButton.Save
        )
        cancel_button = buttons.button(
            QDialogButtonBox.StandardButton.Cancel
        )

        if save_button is not None:
            save_button.setText(
                self._translator.tr(
                    "photos.gps.save"
                )
            )

        if cancel_button is not None:
            cancel_button.setText(
                self._translator.tr(
                    "photos.gps.cancel"
                )
            )

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        restore_requested = {"value": False}

        def request_restore() -> None:
            restore_requested["value"] = True
            dialog.accept()

        restore_button.clicked.connect(
            request_restore
        )

        layout.addWidget(buttons)

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        old_latitude = photo.latitude
        old_longitude = photo.longitude

        try:
            if restore_requested["value"]:
                self._project_service.restore_original_gps(
                    photo.path
                )

                latitude = photo.original_latitude
                longitude = photo.original_longitude

                action_key = "photos.gps.log_restored"
            else:
                latitude = latitude_edit.value()
                longitude = longitude_edit.value()

                self._project_service.set_manual_gps(
                    photo.path,
                    latitude,
                    longitude,
                )

                action_key = "photos.gps.log_changed"

        except Exception as exc:
            self._show_error(str(exc))
            return

        self._log_view.appendPlainText(
            self._translator.tr(
                action_key,
                filename=photo.filename,
                old_latitude=(
                    "—"
                    if old_latitude is None
                    else f"{old_latitude:.7f}"
                ),
                old_longitude=(
                    "—"
                    if old_longitude is None
                    else f"{old_longitude:.7f}"
                ),
                latitude=f"{latitude:.7f}",
                longitude=f"{longitude:.7f}",
            )
        )

        self._load_project_photos()

        self._start_gps_geocoding(
            photo.path,
            latitude,
            longitude,
        )

    def _start_gps_geocoding(
        self,
        photo_path: Path,
        latitude: float,
        longitude: float,
    ) -> None:
        if self._gps_thread is not None:
            self._log_view.appendPlainText(
                self._translator.tr(
                    "photos.gps.geocoding_busy"
                )
            )
            return

        project_path = (
            self._project_service.project_path
        )

        if project_path is None:
            return

        thread = QThread(self)

        worker = GpsGeocodingWorker(
            project_path=project_path,
            latitude=latitude,
            longitude=longitude,
            language=self._language,
            user_agent="PhotoAlbum/0.1 development",
        )

        worker.moveToThread(thread)

        self._gps_photo_path = Path(photo_path)

        thread.started.connect(worker.run)

        worker.completed.connect(
            self._gps_geocoding_completed
        )
        worker.failed.connect(
            self._gps_geocoding_failed
        )

        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)

        thread.finished.connect(
            worker.deleteLater
        )
        thread.finished.connect(
            self._gps_geocoding_thread_finished
        )

        self._gps_thread = thread
        self._gps_worker = worker

        self._log_view.appendPlainText(
            self._translator.tr(
                "photos.gps.geocoding_started"
            )
        )

        thread.start()

    def _gps_geocoding_completed(
        self,
        location,
    ) -> None:
        photo_path = self._gps_photo_path

        if photo_path is None:
            return

        if location is None:
            self._log_view.appendPlainText(
                self._translator.tr(
                    "photos.gps.geocoding_not_found"
                )
            )
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
            self._show_error(str(exc))
            return

        self._log_view.appendPlainText(
            self._translator.tr(
                "photos.gps.geocoding_completed",
                city=location.city or "—",
                address=location.address or "—",
            )
        )

        self._load_project_photos()

    def _gps_geocoding_failed(
        self,
        error: str,
    ) -> None:
        self._log_view.appendPlainText(
            self._translator.tr(
                "photos.gps.geocoding_failed",
                error=error,
            )
        )

    def _gps_geocoding_thread_finished(
        self,
    ) -> None:
        self._gps_thread = None
        self._gps_worker = None
        self._gps_photo_path = None

    def _open_photo_in_os(
        self,
        photo,
    ) -> None:
        path = Path(photo.path)

        if not path.exists():
            self._show_error(
                self._translator.tr(
                    "photos.open_image.not_found",
                    path=path,
                )
            )
            return

        opened = QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(path)
            )
        )

        if not opened:
            self._show_error(
                self._translator.tr(
                    "photos.open_image.error",
                    path=path,
                )
            )

    def _save_photo_caption(
        self,
        photo: Photo,
        caption: str | None,
    ) -> None:
        try:
            self._project_service.set_photo_caption(
                photo.path,
                caption,
            )

            # Captions are part of the rendered album.
            self._preview_render_service.clear()
            self._refresh_album_plan()
            self._update_pdf_summary()
        except Exception as exc:
            self._show_error(str(exc))

    def _go_to_source_photo(
        self,
        photo: Photo,
    ) -> None:
        # Photos is the first main workflow tab.
        self._tabs.setCurrentIndex(0)

        source_model = self._photo_model

        for source_row in range(
            source_model.rowCount()
        ):
            index = source_model.index(
                source_row,
                0,
            )

            candidate = source_model.data(
                index,
                Qt.ItemDataRole.UserRole,
            )

            if (
                isinstance(candidate, Photo)
                and candidate.path == photo.path
            ):
                proxy_index = (
                    self._photo_proxy_model.mapFromSource(
                        index
                    )
                )

                if not proxy_index.isValid():
                    return

                self._photo_table.selectRow(
                    proxy_index.row()
                )
                self._photo_table.scrollTo(
                    proxy_index,
                    QAbstractItemView.ScrollHint.PositionAtCenter,
                )
                self._photo_table.setFocus()
                return

    def _save_photo_editorial_location(
        self,
        photo: Photo,
        components,
        location_text: str | None,
    ) -> None:
        try:
            self._project_service.set_editorial_location(
                photo.path,
                components=components,
                location_text=location_text,
            )

            # The album composition and rendered previews depend on
            # the effective editorial location. Rebuild them
            # immediately after a location edit.
            self._preview_render_service.clear()
            self._refresh_album_plan()
            self._update_pdf_summary()
        except Exception as exc:
            self._show_error(str(exc))

    def eventFilter(
        self,
        watched,
        event,
    ) -> bool:
        if (
            hasattr(self, "_photo_table")
            and watched is self._photo_table.viewport()
        ):
            if event.type() == QEvent.Type.MouseMove:
                position = event.position().toPoint()
                index = self._photo_table.indexAt(position)

                if (
                    index.isValid()
                    and index.column() == 0
                ):
                    row = index.row()

                    if row != self._source_preview_row:
                        self._cancel_source_photo_preview()
                        self._source_preview_row = row

                    self._source_preview_position = (
                        event.globalPosition().toPoint()
                    )

                    if (
                        self._source_preview is None
                        and not self._source_preview_timer.isActive()
                    ):
                        self._source_preview_timer.start()
                else:
                    self._cancel_source_photo_preview()

            elif event.type() in (
                QEvent.Type.Leave,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.Wheel,
            ):
                self._cancel_source_photo_preview()

        return super().eventFilter(
            watched,
            event,
        )

    def _show_pending_source_photo_preview(self) -> None:
        if self._source_preview_row is None:
            return

        proxy_index = self._photo_proxy_model.index(
            self._source_preview_row,
            0,
        )

        if not proxy_index.isValid():
            return

        source_index = self._photo_proxy_model.mapToSource(
            proxy_index
        )

        photo = self._photo_model.photo_at(
            source_index.row()
        )

        if photo is None:
            return

        reader = QImageReader(str(photo.path))
        reader.setAutoTransform(True)

        image = reader.read()

        if image.isNull():
            return

        pixmap = QPixmap.fromImage(image).scaled(
            420,
            320,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        preview = QLabel(
            None,
            Qt.WindowType.ToolTip,
        )
        preview.setPixmap(pixmap)
        preview.setFrameShape(
            QFrame.Shape.Box
        )
        preview.setContentsMargins(
            4,
            4,
            4,
            4,
        )
        preview.adjustSize()

        preview.move(
            self._source_preview_position
            + QPoint(16, 20)
        )
        preview.show()

        self._source_preview = preview

    def _hide_source_photo_preview(self) -> None:
        if self._source_preview is not None:
            self._source_preview.close()
            self._source_preview.deleteLater()
            self._source_preview = None

    def _cancel_source_photo_preview(self) -> None:
        self._source_preview_timer.stop()
        self._hide_source_photo_preview()
        self._source_preview_row = None

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(
            self,
            "Photo Album",
            message,
        )

    def _load_project_photos(self) -> None:
        if not self._project_service.is_open:
            self._photo_model.clear()
            return

        photos = self._project_service.list_photos()

        self._photo_model.set_photos(photos)
        self._photos_places_widget.set_photos(photos)
        self._update_album_years(photos)

        total = len(photos)

        date_anomalies = sum(
            1
            for photo in photos
            if photo.is_date_anomaly
        )

        gps_photos = sum(
            1
            for photo in photos
            if photo.has_gps
        )

        located_photos = sum(
            1
            for photo in photos
            if photo.location_source.value != "unknown"
        )

        self._summary_label.setText(
            " | ".join(
                [
                    self._translator.tr(
                        "main.stored_photos",
                        count=total,
                    ),
                    self._translator.tr(
                        "main.gps",
                        count=gps_photos,
                    ),
                    self._translator.tr(
                        "main.located",
                        count=located_photos,
                    ),
                    self._translator.tr(
                        "main.date_anomalies",
                        count=date_anomalies,
                    ),
                ]
            )
        )
        self._refresh_album_plan()
        self._update_pdf_summary()
