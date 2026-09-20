from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QTabWidget,
)

from photoalbum import __version__
from photoalbum.app import ProjectService
from photoalbum.gui.help_dialog import HelpDialog
from photoalbum.gui.template_pack_help_dialog import (
    TemplatePackHelpDialog,
)

from photoalbum.album import (
    AlbumBuilder,
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
from photoalbum.gui.scan_controller import ScanController
from photoalbum.gui.photo_editor import PhotoEditor
from photoalbum.gui.widgets.pdf_export_widget import PdfExportWidget
from photoalbum.gui.widgets.photo_sources_widget import PhotoSourcesWidget
from photoalbum.models import Photo


class MainWindow(QMainWindow):
    """Coordinate the project, workflow tabs and shared album state."""

    def __init__(self, *, language: str = "en") -> None:
        super().__init__()

        self._language = language
        self._project_service = ProjectService()
        self._translator = Translator(self._language)

        self._preview_render_service = PreviewRenderService(self._translator, self)

        self._template_registry = create_template_registry()

        register_discovered_template_extensions()
        self._album_build_result = None

        self._album_builder = AlbumBuilder(self._template_registry)

        # Editorial changes made in "Places and captions" are
        # persisted immediately, but rebuilding the whole album is
        # deferred until the user leaves that tab.
        self._editorial_album_dirty = False
        self._previous_tab_index = 0

        self.setWindowTitle("Photo Album")
        self.resize(1100, 700)

        self._photo_editor = PhotoEditor(
            self._project_service, self._translator, language=language, parent=self,
        )
        self._photo_editor.error.connect(self._show_error)
        self._photo_editor.photos_changed.connect(self._load_project_photos)
        self._create_actions()
        self._create_menu()
        self._create_status_bar()
        self._create_content()

        self._update_project_state()

    def closeEvent(self, event) -> None:
        if self._pdf_widget.is_running:
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

        if self._scan_controller.is_running:
            QMessageBox.warning(
                self,
                "Photo Album",
                self._translator.tr('main.scan_running_warning'),
            )
            event.ignore()
            return

        self._project_service.close()
        super().closeEvent(event)

    def _create_actions(self) -> None:
        self._new_project_action = QAction(self._translator.tr('main.new_project'), self)
        self._new_project_action.triggered.connect(self._new_project)

        self._open_project_action = QAction(self._translator.tr('main.open_project'), self)
        self._open_project_action.triggered.connect(self._open_project)

        self._close_project_action = QAction(self._translator.tr('main.close_project'), self)
        self._close_project_action.triggered.connect(self._close_project)

        self._quit_action = QAction(self._translator.tr('main.quit'), self)
        self._quit_action.triggered.connect(self.close)

        self._help_action = QAction(self._translator.tr('main.quick_help'), self)
        self._help_action.triggered.connect(self._show_help_dialog)

        self._template_help_action = QAction(
            self._translator.tr("main.template_help"),
            self,
        )
        self._template_help_action.triggered.connect(
            self._show_template_help_dialog
        )

        self._about_action = QAction(self._translator.tr('main.about'), self)
        self._about_action.triggered.connect(self._show_about_dialog)

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu(self._translator.tr("main.file"))

        file_menu.addAction(self._new_project_action)
        file_menu.addAction(self._open_project_action)
        file_menu.addAction(self._close_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self._quit_action)

        help_menu = self.menuBar().addMenu(self._translator.tr('main.help'))
        help_menu.addAction(self._help_action)
        help_menu.addAction(self._template_help_action)
        help_menu.addSeparator()
        help_menu.addAction(self._about_action)

    def _show_help_dialog(self) -> None:
        """Display the localized quick help dialog."""
        dialog = HelpDialog(self._translator, self)
        dialog.exec()

    def _show_template_help_dialog(self) -> None:
        """Display documentation supplied by template packs."""
        dialog = TemplatePackHelpDialog(
            self._translator,
            self,
        )
        dialog.exec()

    def _show_about_dialog(self) -> None:
        """Display information about Photo Album."""
        dialog = QDialog(self)
        dialog.setWindowTitle(self._translator.tr('about.window_title'))
        dialog.setMinimumWidth(700)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(32, 24, 32, 20)
        layout.setSpacing(14)

        title = QLabel("Photo Album")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('font-size: 26px; font-weight: bold;')
        layout.addWidget(title)

        version_label = QLabel(self._translator.tr('about.version', version=__version__))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        slogan = QLabel(self._translator.tr('about.slogan'))
        slogan.setWordWrap(True)
        slogan.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slogan.setStyleSheet('font-size: 15px; font-weight: bold;')
        layout.addWidget(slogan)

        # Keep the complete body in one label so Qt can calculate
        # the wrapped height naturally as a single document.
        body = QLabel(
            self._translator.tr('about.description') + '<br><br>'
            + self._translator.tr("about.author")
            + "<br><br>"
            + self._translator.tr("about.license")
        )
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        body.setOpenExternalLinks(True)
        layout.addWidget(body)

        dedication = QLabel(self._translator.tr('about.dedication'))
        dedication.setTextFormat(Qt.TextFormat.RichText)
        dedication.setWordWrap(True)
        dedication.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dedication)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.adjustSize()
        dialog.exec()

    def _create_content(self) -> None:
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        self._project_label = QLabel()
        self._project_label.setStyleSheet('font-size: 20px; font-weight: bold;')

        layout.addWidget(self._project_label)

        # ----------------------------------------------------
        # Main project workflow
        # ----------------------------------------------------

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, 1)

        # ----------------------------------------------------
        # Photos
        # ----------------------------------------------------

        self._photos_widget = PhotoSourcesWidget(self._translator, self)
        self._scan_controller = ScanController(
            self._project_service, self._photos_widget, self._translator,
            language=self._language, parent=self,
        )
        self._scan_controller.error.connect(self._show_error)
        self._scan_controller.status_message.connect(self.statusBar().showMessage)
        self._scan_controller.running_changed.connect(self._set_scan_running)
        self._scan_controller.photos_ready.connect(self._scan_photos_ready)
        self._scan_controller.source_unavailable.connect(lambda: self._tabs.setCurrentIndex(0))
        self._photos_widget.source_requested.connect(self._choose_source_directory)
        self._photos_widget.recursive_changed.connect(self._recursive_changed)
        self._photos_widget.scan_requested.connect(self._scan_controller.toggle)
        self._photos_widget.edit_datetime_requested.connect(self._photo_editor.edit_datetime)
        self._photos_widget.edit_gps_requested.connect(self._photo_editor.edit_gps)
        self._photos_widget.open_photo_requested.connect(self._photo_editor.open_in_os)
        self._photo_editor.log_message.connect(self._photos_widget.log_view.appendPlainText)
        self._tabs.addTab(self._photos_widget, self._translator.tr("tab.photos"))

        # ----------------------------------------------------
        # Places and captions
        # ----------------------------------------------------

        self._photos_places_widget = PhotoPlacesWidget(
            translator=self._translator,
            save_location=self._save_photo_editorial_location,
            save_caption=self._save_photo_caption,
            save_locations=self._save_photo_editorial_locations,
            edit_source_photo=self._go_to_source_photo,
            parent=self,
        )

        self._photos_places_index = (
            self._tabs.addTab(
                self._photos_places_widget,
                self._translator.tr('tab.places_captions'),
            )
        )

        self._album_settings_widget = AlbumSettingsWidget(
            self._template_registry,
            translator=self._translator,
            parent=self,
            render_service=self._preview_render_service,
        )

        self._album_settings_widget.set_photo_provider(self._project_service.list_photos)

        self._album_settings_widget.settings_changed.connect(self._save_album_settings)

        self._tabs.addTab(self._album_settings_widget, self._translator.tr('tab.album'))

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

        self._tabs.addTab(self._album_plan_widget, self._translator.tr('tab.plan'))

        self._tabs.addTab(self._album_preview_widget, self._translator.tr('tab.preview'))

        # ----------------------------------------------------
        # Final rendering / PDF tab
        # ----------------------------------------------------

        self._pdf_widget = PdfExportWidget(
            translator=self._translator,
            project_service=self._project_service,
            settings_provider=self._album_settings_widget.settings,
            result_provider=lambda: self._album_build_result,
            before_export=self._flush_editorial_album_changes,
            parent=self,
        )
        self._pdf_widget.error.connect(self._show_error)
        self._pdf_widget.status_message.connect(self.statusBar().showMessage)
        self._tabs.addTab(self._pdf_widget, self._translator.tr("tab.render"))

        self._previous_tab_index = self._tabs.currentIndex()
        self._tabs.currentChanged.connect(self._main_tab_changed)

        self.setCentralWidget(central_widget)

    def _mark_editorial_album_dirty(self) -> None:
        self._editorial_album_dirty = True

    def _flush_editorial_album_changes(self) -> None:
        if not self._editorial_album_dirty:
            return

        if not self._project_service.is_open:
            self._editorial_album_dirty = False
            return

        self._preview_render_service.clear()
        self._refresh_album_plan()
        self._update_pdf_summary()
        self._editorial_album_dirty = False

    def _main_tab_changed(self, index: int) -> None:
        previous = self._previous_tab_index
        self._previous_tab_index = index

        if previous == self._photos_places_index and index != self._photos_places_index:
            self._flush_editorial_album_changes()

    def _update_pdf_summary(self) -> None:
        self._pdf_widget.update_summary()

    def _create_status_bar(self) -> None:
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

    def _new_project(self) -> None:
        self._preview_render_service.clear()
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._translator.tr('main.new_project'),
            "",
            "Photo Album Project (*.photoalbum)",
        )

        if not path:
            return

        project_path = Path(path)

        if project_path.suffix != ".photoalbum":
            project_path = project_path.with_suffix('.photoalbum')

        try:
            # QFileDialog already asked the user whether the
            # existing file may be replaced. Honour that choice.
            if self._project_service.is_open:
                self._project_service.close()

            if project_path.exists():
                project_path.unlink()

            self._project_service.create(project_path)

        except Exception as exc:
            self._show_error(str(exc))
            return

        self._scan_controller.reset()

        self._photos_widget.source_edit.clear()

        previous = self._photos_widget.recursive_checkbox.blockSignals(True)

        self._photos_widget.recursive_checkbox.setChecked(False)

        self._photos_widget.recursive_checkbox.blockSignals(previous)

        self._photos_widget.summary_label.setText(self._translator.tr('main.no_analysis'))

        self._photos_widget.log_view.clear()
        self._photos_widget.model.clear()

        self._album_settings_widget.reset_to_defaults()
        self._album_settings_widget.set_available_years(set())

        self._album_plan_widget.clear()
        self._album_preview_widget.clear()

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

        self._open_project_path(Path(path))

    def _open_project_path(self, path: Path) -> None:
        """Open an existing project from an explicit path."""
        self._preview_render_service.clear()

        try:
            self._project_service.open(path)
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
        if self._photos_widget.source_edit.text().strip():
            self._scan_controller.start()

    def _close_project(self) -> None:
        self._preview_render_service.clear()
        self._album_build_result = None
        self._project_service.close()

        self._scan_controller.reset()

        self._album_plan_widget.clear()
        self._album_preview_widget.clear()

        self._photos_widget.source_edit.clear()
        self._photos_widget.recursive_checkbox.setChecked(False)
        self._photos_widget.summary_label.setText(self._translator.tr('main.no_analysis'))
        self._photos_widget.log_view.clear()
        self._photos_widget.model.clear()
        self._photos_places_widget.clear()
        self._album_settings_widget.set_available_years(set())
        self._album_settings_widget.reset_to_defaults()
        self._album_plan_widget.clear()
        self._update_project_state()

    def _choose_source_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            self._translator.tr('main.choose_source'),
        )

        if not directory:
            return

        try:
            self._project_service.set_source_directory(Path(directory))
        except Exception as exc:
            self._show_error(str(exc))
            return

        self._photos_widget.source_edit.setText(directory)

        self._scan_controller.reset()

        self._update_project_state()

        # Choosing a source folder defines the photo library:
        # analysis therefore starts immediately.
        self._scan_controller.start()

    def _recursive_changed(self, checked: bool) -> None:
        if not self._project_service.is_open:
            return

        self._project_service.set_recursive_scan(checked)

        source_directory = self._project_service.get_source_directory()

        if source_directory is not None and not self._scan_controller.is_running:
            self._scan_controller.reset()
            self._scan_controller.start()

    def _load_project_settings(self) -> None:
        source_directory = self._project_service.get_source_directory()

        self._photos_widget.source_edit.setText(
            str(source_directory) if source_directory is not None else ''
        )

        self._photos_widget.recursive_checkbox.setChecked(
            self._project_service.get_recursive_scan()
        )

        album_settings = self._project_service.get_album_structure_settings()

        if album_settings is None:
            self._album_settings_widget.reset_to_defaults()
        else:
            self._album_settings_widget.set_settings(album_settings)

    def _set_scan_running(self, running: bool) -> None:
        self._new_project_action.setEnabled(not running)

        self._open_project_action.setEnabled(not running)

        self._close_project_action.setEnabled(not running and self._project_service.is_open)

        self._photos_widget.browse_button.setEnabled(
            (
                not running and self._project_service.is_open
            )
        )

        self._photos_widget.recursive_checkbox.setEnabled(
            (
                not running and self._project_service.is_open
            )
        )

        self._photos_widget.analyze_button.setEnabled(
            (
                running
                or (
                    self._project_service.is_open
                    and bool(self._photos_widget.source_edit.text())
                )
            )
        )

        # Photos remains the project entry point. Every other
        # workflow tab is available as soon as the project contains
        # photos and no scan is currently running.
        photos_available = (
            self._project_service.is_open
            and not running
            and bool(self._project_service.list_photos())
        )

        # Photos is always available. It is the entry point
        # for creating/opening a project, selecting the source
        # folder and reading the analysis log.
        if self._tabs.count() > 0:
            self._tabs.setTabEnabled(0, True)

        for index in range(1, self._tabs.count()):
            self._tabs.setTabEnabled(index, photos_available)

        self._photos_widget.progress_bar.setVisible(running)

        if running:
            self._photos_widget.analyze_button.setText(
                self._translator.tr('main.stop_analysis')
            )

            self.statusBar().showMessage(self._translator.tr('main.analysis_in_progress'))

        else:
            if self._scan_controller.analysis_completed:
                self._photos_widget.analyze_button.setText(
                    self._translator.tr('main.analyze_again')
                )
            else:
                self._photos_widget.analyze_button.setText(
                    self._translator.tr('main.analyze_photos')
                )

    def _update_project_state(self) -> None:
        is_open = self._project_service.is_open
        has_source = bool(self._photos_widget.source_edit.text())

        self._close_project_action.setEnabled(is_open)
        self._photos_widget.browse_button.setEnabled(is_open)
        self._photos_widget.recursive_checkbox.setEnabled(is_open)
        self._photos_widget.analyze_button.setEnabled(is_open and has_source)

        if is_open:
            project_path = self._project_service.project_path

            self._project_label.setText(
                self._translator.tr('main.project', name=project_path.name)
            )

            self.statusBar().showMessage(str(project_path))
        else:
            self._project_label.setText(self._translator.tr('main.no_project'))
            self.statusBar().showMessage(self._translator.tr("main.ready"))

        # Re-evaluate tab availability as part of every
        # project-state refresh.
        self._set_scan_running(self._scan_controller.is_running)

    def _update_album_years(self, photos) -> None:
        years = {
            photo.capture_datetime.year
            for photo in photos
            if photo.capture_datetime is not None
        }

        self._album_settings_widget.set_available_years(years)

    def _prewarm_expensive_previews(self, result, settings, photos) -> None:
        """
        Pre-render expensive templates using exactly the same
        photo set as the album preview.

        Do NOT use the raw repository photo list here: the album
        plan may exclude undated/anomalous photos or otherwise
        expose a different ordering.
        """

        page_format = settings.effective_page_format()

        project_photos = []
        seen_paths = set()

        for item in result.plan.items:
            for photo in item.photos:
                key = str(photo.path)

                if key in seen_paths:
                    continue

                seen_paths.add(key)

                project_photos.append(photo)

        instances = []

        # Covers.
        for cover in settings.covers.values():
            page = cover.page

            if self._preview_render_service.supports(page.template_id):
                instances.append(page)

        # Special-page instances.
        for item in result.plan.items:
            page = item.page_instance
            if page is not None and self._preview_render_service.supports(page.template_id):
                instances.append(page)

        seen_instances = set()

        for instance in instances:
            if instance.instance_id in seen_instances:
                continue

            seen_instances.add(instance.instance_id)

            self._preview_render_service.request(
                instance,
                project_photos,
                width=PREVIEW_RENDER_WIDTH,
                height=PREVIEW_RENDER_HEIGHT,
                page_width_mm=page_format.width_mm,
                page_height_mm=page_format.height_mm,
            )

    def _refresh_album_plan(self) -> None:
        if not self._project_service.is_open:
            self._album_plan_widget.clear()
            self._album_preview_widget.clear()
            return

        try:
            photos = self._project_service.list_photos()

            settings = self._album_settings_widget.settings()

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

            self._album_plan_widget.set_result(result, settings)

            page_format = settings.effective_page_format()

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
                self._prewarm_expensive_previews(result, settings, photos)
            except Exception:
                pass

        except Exception as exc:
            self._album_plan_widget.clear()
            self._album_preview_widget.clear()

            self.statusBar().showMessage(
                self._translator.tr('main.build_plan_error', error=exc)
            )

    def _save_album_settings(self) -> None:
        if not self._project_service.is_open:
            return

        try:
            settings = self._album_settings_widget.settings()

            self._project_service.set_album_structure_settings(settings)
            self._refresh_album_plan()
            self._update_pdf_summary()
        except Exception as exc:
            self._show_error(self._translator.tr('main.save_album_error', error=exc))

    def _save_photo_caption(self, photo: Photo, caption: str | None) -> None:
        try:
            self._project_service.set_photo_caption(photo.path, caption)

            # Persist immediately, but defer the expensive album
            # rebuild until "Places and captions" is left.
            self._mark_editorial_album_dirty()
        except Exception as exc:
            self._show_error(str(exc))

    def _go_to_source_photo(self, photo: Photo) -> None:
        self._tabs.setCurrentIndex(0)
        self._photos_widget.select_photo(photo)

    def _save_photo_editorial_locations(self, changes) -> None:
        """
        Persist a grouped editorial-location edit and mark the
        album for one deferred refresh.
        """
        changed = False

        try:
            for photo, components, location_text in changes:
                self._project_service.set_editorial_location(
                    photo.path,
                    components=components,
                    location_text=location_text,
                )
                changed = True
        except Exception as exc:
            self._show_error(str(exc))
        finally:
            if changed:
                self._mark_editorial_album_dirty()

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

            # Persist immediately, but defer the expensive album
            # rebuild until "Places and captions" is left.
            self._mark_editorial_album_dirty()
        except Exception as exc:
            self._show_error(str(exc))

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, 'Photo Album', message)

    def _load_project_photos(self) -> None:
        if not self._project_service.is_open:
            self._photos_widget.model.clear()
            return

        photos = self._project_service.list_photos()

        self._photos_widget.model.set_photos(photos)
        self._photos_places_widget.set_photos(photos)
        self._update_album_years(photos)

        total = len(photos)

        date_anomalies = sum((1 for photo in photos if photo.is_date_anomaly))

        gps_photos = sum((1 for photo in photos if photo.has_gps))

        located_photos = sum(1 for photo in photos if photo.location_source.value != 'unknown')

        self._photos_widget.summary_label.setText(
            " | ".join(
                [
                    self._translator.tr('main.stored_photos', count=total),
                    self._translator.tr('main.gps', count=gps_photos),
                    self._translator.tr('main.located', count=located_photos),
                    self._translator.tr('main.date_anomalies', count=date_anomalies),
                ]
            )
        )
        self._refresh_album_plan()
        self._update_pdf_summary()

    def _scan_photos_ready(self, photos: list[Photo]) -> None:
        self._photos_widget.model.set_photos(photos)
        self._photos_places_widget.set_photos(photos)
        self._update_album_years(photos)
        self._refresh_album_plan()
        self._update_pdf_summary()
