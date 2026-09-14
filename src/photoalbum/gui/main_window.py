from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QSortFilterProxyModel,
    QThread,
    Qt,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
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

from photoalbum.app import ProjectService
from photoalbum.gui.models import PhotoTableModel
from photoalbum.gui.workers import ScanWorker
from photoalbum.scanner import (
    LibraryScanResult,
    ProcessingEvent,
)

from photoalbum.album import (
    AlbumBuilder,
    create_builtin_template_registry,
)
from photoalbum.gui.widgets import (
    AlbumPlanWidget,
    AlbumSettingsWidget,
)
from photoalbum.i18n import Translator
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self._project_service = ProjectService()
        self._translator = Translator("fr")

        self._template_registry = (
            create_builtin_template_registry()
        )
        self._album_builder = AlbumBuilder(
            self._template_registry
        )
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None

        self.setWindowTitle("Photo Album")
        self.resize(1100, 700)

        self._create_actions()
        self._create_menu()
        self._create_content()
        self._create_status_bar()

        self._update_project_state()

    def closeEvent(self, event) -> None:
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

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu(self._translator.tr("main.file"))

        file_menu.addAction(self._new_project_action)
        file_menu.addAction(self._open_project_action)
        file_menu.addAction(self._close_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self._quit_action)

    def _create_content(self) -> None:
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        self._project_label = QLabel()
        self._project_label.setStyleSheet(
            "font-size: 20px; font-weight: bold;"
        )

        layout.addWidget(self._project_label)

        source_layout = QHBoxLayout()

        self._source_edit = QLineEdit()
        self._source_edit.setReadOnly(True)

        self._browse_source_button = QPushButton(
            self._translator.tr("main.choose_source")
        )
        self._browse_source_button.clicked.connect(
            self._choose_source_directory
        )

        source_layout.addWidget(QLabel(self._translator.tr("main.source_folder")))
        source_layout.addWidget(self._source_edit, 1)
        source_layout.addWidget(self._browse_source_button)

        layout.addLayout(source_layout)

        self._recursive_checkbox = QCheckBox(
            self._translator.tr("main.include_subdirectories")
        )
        self._recursive_checkbox.toggled.connect(
            self._recursive_changed
        )

        layout.addWidget(self._recursive_checkbox)

        action_layout = QHBoxLayout()

        self._analyze_button = QPushButton(
            self._translator.tr("main.analyze_photos")
        )
        self._analyze_button.clicked.connect(
            self._start_scan
        )

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)

        action_layout.addWidget(self._analyze_button)
        action_layout.addWidget(self._progress_bar, 1)

        layout.addLayout(action_layout)

        self._summary_label = QLabel(
            self._translator.tr("main.no_analysis")
        )
        layout.addWidget(self._summary_label)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, 1)

        photos_tab = QWidget()
        photos_layout = QVBoxLayout(photos_tab)


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

        self._photo_table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )
        self._photo_table.setSelectionMode(
            QTableView.SelectionMode.SingleSelection
        )
        self._photo_table.setAlternatingRowColors(True)
        self._photo_table.setSortingEnabled(True)

        self._photo_table.sortByColumn(
            1,
            Qt.SortOrder.AscendingOrder,
        )

        header = self._photo_table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        header.setStretchLastSection(True)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)

        splitter = QSplitter(
            Qt.Orientation.Vertical
        )

        splitter.addWidget(self._photo_table)
        splitter.addWidget(self._log_view)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        photos_layout.addWidget(
            QLabel(self._translator.tr("main.photos"))
        )
        photos_layout.addWidget(splitter, 1)

        self._tabs.addTab(
            photos_tab,
            self._translator.tr("tab.photos"),
        )

        self._album_settings_widget = AlbumSettingsWidget(
            self._template_registry,
            translator=self._translator,
            parent=self,
        )

        self._album_settings_widget.settings_changed.connect(
            self._save_album_settings
        )

        self._tabs.addTab(
            self._album_settings_widget,
            self._translator.tr("tab.album"),
        )

        self._album_plan_widget = AlbumPlanWidget(
            translator=self._translator,
            parent=self,
        )

        self._tabs.addTab(
            self._album_plan_widget,
            self._translator.tr("tab.plan"),
        )
        self.setCentralWidget(central_widget)

    def _create_status_bar(self) -> None:
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

    def _new_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._translator.tr("main.create_project_title"),
            "",
            "Photo Album Project (*.photoalbum)",
        )

        if not path:
            return

        project_path = Path(path)

        if project_path.suffix != ".photoalbum":
            project_path = project_path.with_suffix(
                ".photoalbum"
            )

        try:
            self._project_service.create(project_path)
        except Exception as exc:
            self._show_error(str(exc))
            return

        self._load_project_settings()
        self._load_project_photos()
        self._update_project_state()

    def _open_project(self) -> None:
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

    def _close_project(self) -> None:
        self._project_service.close()

        self._source_edit.clear()
        self._recursive_checkbox.setChecked(False)
        self._summary_label.setText(
            self._translator.tr("main.no_analysis")
        )
        self._log_view.clear()
        self._photo_model.clear()
        self._album_settings_widget.set_available_years(
            set()
        )
        self._album_settings_widget.reset_to_defaults()
        self._album_plan_widget.clear()
        self._update_project_state()

    def _choose_source_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            self._translator.tr("main.choose_source_title"),
        )

        if not directory:
            return

        try:
            self._project_service.set_source_directory(
                Path(directory)
            )
        except Exception as exc:
            self._show_error(str(exc))
            return

        self._source_edit.setText(directory)
        self._update_project_state()

    def _recursive_changed(
        self,
        checked: bool,
    ) -> None:
        if not self._project_service.is_open:
            return

        self._project_service.set_recursive_scan(checked)

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
            self._show_error(
                self._translator.tr(
                    "main.source_missing_error",
                    path=source_directory,
                )
            )
            return

        self._log_view.clear()
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
            language="fr",
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

    def _handle_processing_event(
        self,
        event: ProcessingEvent,
    ) -> None:
        self._log_view.appendPlainText(
            f"[{event.type.value}] "
            f"{event.path.name}: "
            f"{event.message}"
        )

    def _scan_completed(
        self,
        result: LibraryScanResult,
    ) -> None:
        statistics = result.statistics

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
        self._update_album_years(all_photos)
        self._refresh_album_plan()

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

        self._set_scan_running(False)

    def _set_scan_running(
        self,
        running: bool,
    ) -> None:
        self._new_project_action.setEnabled(not running)
        self._open_project_action.setEnabled(not running)
        self._close_project_action.setEnabled(
            not running
            and self._project_service.is_open
        )

        self._browse_source_button.setEnabled(
            not running
            and self._project_service.is_open
        )

        self._recursive_checkbox.setEnabled(
            not running
            and self._project_service.is_open
        )

        self._analyze_button.setEnabled(
            not running
            and self._project_service.is_open
            and bool(self._source_edit.text())
        )

        self._progress_bar.setVisible(running)

        if running:
            self._progress_bar.setRange(0, 0)
            self.statusBar().showMessage(
                self._translator.tr("main.analyzing")
            )
        else:
            self._progress_bar.setRange(0, 1)

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

    def _refresh_album_plan(self) -> None:
        if not self._project_service.is_open:
            self._album_plan_widget.clear()
            return

        try:
            photos = self._project_service.list_photos()

            settings = (
                self._album_settings_widget.settings()
            )

            result = self._album_builder.build(
                photos,
                settings,
            )

            self._album_plan_widget.set_result(
                result
            )

        except Exception as exc:
            self._album_plan_widget.clear()

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
        except Exception as exc:
            self._show_error(
                self._translator.tr(
                    "main.save_album_error",
                    error=exc,
                )
            )

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