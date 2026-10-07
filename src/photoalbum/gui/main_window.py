from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThreadPool, Slot
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QToolButton,
    QInputDialog,
    QHBoxLayout,
    QMessageBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QTabWidget,
)

from photoalbum.app_info import APPLICATION_NAME, VERSION
from photoalbum.app import ProjectService
from photoalbum.gui.help_dialog import HelpDialog
from photoalbum.gui.icon_resources import resource_icon
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
from photoalbum.gui.hover_photo_preview import HoverPhotoPreview
from photoalbum.gui.preview_image_cache import PreviewImageCache
from photoalbum.template_engine import (
    create_template_registry,
    register_discovered_template_extensions,
)
from photoalbum.i18n import Translator
from photoalbum.gui.scan_controller import ScanController
from photoalbum.gui.photo_editor import PhotoEditor
from photoalbum.gui.workers.legacy_cache_cleanup_worker import LegacyCacheCleanupWorker
from photoalbum.gui.synology_source_dialog import SynologySourceDialog
from photoalbum.gui.widgets.pdf_export_widget import PdfExportWidget
from photoalbum.gui.widgets.photo_sources_widget import PhotoSourcesWidget
from photoalbum.models import Photo
from photoalbum.project_metadata import PdfExportSettings, ProjectPdfMetadata


class MainWindow(QMainWindow):
    """Coordinate the project, workflow tabs and shared album state."""

    def __init__(self, *, language: str = "en") -> None:
        super().__init__()

        self._language = language
        self._project_service = ProjectService()
        self._legacy_cache_workers = {}
        self._translator = Translator(self._language)

        self._preview_render_service = PreviewRenderService(self._translator, self)
        self._hover_preview_cache = PreviewImageCache(self)
        self._hover_photo_preview = HoverPhotoPreview(
            self._hover_preview_cache,
            self,
        )

        self._template_registry = create_template_registry()

        register_discovered_template_extensions()
        self._album_build_result = None

        self._album_builder = AlbumBuilder(self._template_registry)

        # Editorial changes made in "Places and captions" are
        # persisted immediately, but rebuilding the whole album is
        # deferred until the user leaves that tab.
        self._editorial_album_dirty = False
        self._previous_tab_index = 0

        self.setWindowTitle(APPLICATION_NAME)
        self._restore_or_set_initial_geometry()

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


    def _restore_or_set_initial_geometry(self) -> None:
        """Restore the previous window geometry or choose a screen-safe default."""
        settings = QSettings("PhotoAlbum", APPLICATION_NAME)
        saved_geometry = settings.value("main_window/geometry")
        if saved_geometry is not None and self.restoreGeometry(saved_geometry):
            return

        screen = self.screen()
        if screen is None:
            self.resize(1100, 700)
            return

        available = screen.availableGeometry()
        width = min(available.width(), max(1000, int(available.width() * 0.90)), 1440)
        height = min(available.height(), max(650, int(available.height() * 0.90)), 900)
        self.resize(width, height)

    def closeEvent(self, event) -> None:
        if self._pdf_widget.is_running:
            QMessageBox.warning(
                self,
                APPLICATION_NAME,
                self._translator.tr('main.pdf_running_warning'),
            )
            event.ignore()
            return

        if self._scan_controller.is_running:
            QMessageBox.warning(
                self,
                APPLICATION_NAME,
                self._translator.tr('main.scan_running_warning'),
            )
            event.ignore()
            return

        QSettings("PhotoAlbum", APPLICATION_NAME).setValue(
            "main_window/geometry",
            self.saveGeometry(),
        )
        self._pdf_widget.save_project_settings()
        self._hover_photo_preview.clear()
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

        self._cache_action = QAction(self._translator.tr("cache.title"), self)
        self._cache_action.triggered.connect(self._show_cache_dialog)

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

        settings_menu = self.menuBar().addMenu(self._translator.tr("main.settings"))
        settings_menu.addAction(self._cache_action)

        help_menu = self.menuBar().addMenu(self._translator.tr('main.help'))
        help_menu.addAction(self._help_action)
        help_menu.addAction(self._template_help_action)
        help_menu.addSeparator()
        help_menu.addAction(self._about_action)

    def _show_cache_dialog(self) -> None:
        from photoalbum.gui.cache_dialog import CacheDialog
        dialog = CacheDialog(
            self._translator, self,
            project_is_open=lambda: self._project_service.is_open,
        )
        dialog.exec()

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

        title = QLabel(APPLICATION_NAME)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('font-size: 26px; font-weight: bold;')
        layout.addWidget(title)

        version_label = QLabel(self._translator.tr('about.version', version=VERSION))
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

        project_header = QHBoxLayout()
        project_header.setContentsMargins(0, 0, 0, 0)
        project_header.setSpacing(6)

        self._project_label = QLabel()
        self._project_label.setStyleSheet('font-size: 20px; font-weight: bold;')
        project_header.addWidget(self._project_label)

        self._project_rename_button = QToolButton()
        self._project_rename_button.setIcon(resource_icon("plan-edit.svg"))
        self._project_rename_button.setAutoRaise(True)
        self._project_rename_button.setToolTip(
            self._translator.tr("main.rename_project")
        )
        self._project_rename_button.clicked.connect(self._rename_project)
        project_header.addWidget(self._project_rename_button)

        self._project_filename_label = QLabel()
        filename_palette = self._project_filename_label.palette()
        filename_palette.setColor(
            QPalette.ColorRole.WindowText,
            filename_palette.color(QPalette.ColorRole.PlaceholderText),
        )
        self._project_filename_label.setPalette(filename_palette)
        self._project_filename_label.setStyleSheet('font-size: 13px;')
        project_header.addWidget(self._project_filename_label)
        project_header.addStretch(1)

        layout.addLayout(project_header)

        # ----------------------------------------------------
        # Main project workflow
        # ----------------------------------------------------

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, 1)

        # ----------------------------------------------------
        # Photos
        # ----------------------------------------------------

        self._photos_widget = PhotoSourcesWidget(
            self._translator,
            self,
            hover_preview=self._hover_photo_preview,
        )
        self._scan_controller = ScanController(
            self._project_service, self._photos_widget, self._translator,
            language=self._language, parent=self,
        )
        self._pending_nominatim_location_sources: set[str] = set()
        self._scan_controller.error.connect(self._show_error)
        self._scan_controller.status_message.connect(self._show_transient_status)
        self._scan_controller.metadata_refresh_finished.connect(
            self._metadata_refresh_finished
        )
        self._scan_controller.running_changed.connect(self._set_scan_running)
        self._scan_controller.photos_ready.connect(self._scan_photos_ready)
        self._scan_controller.source_unavailable.connect(lambda: self._tabs.setCurrentIndex(0))
        self._scan_controller.source_changed.connect(
            self._source_import_completed
        )
        self._photos_widget.source_requested.connect(self._choose_source_directory)
        self._photos_widget.synology_source_requested.connect(
            self._choose_synology_source
        )
        # Global refresh/synchronization entry points remain available in the
        # controller for automatic/internal workflows, but the Photos UI now
        # exposes synchronization directly on each source card.
        self._photos_widget.source_sync_requested.connect(
            self._scan_controller.sync_source
        )
        self._photos_widget.scan_requested.connect(self._scan_controller.cancel)
        self._photos_widget.edit_datetime_requested.connect(self._photo_editor.edit_datetime)
        self._photos_widget.edit_gps_requested.connect(self._photo_editor.edit_gps)
        self._photos_widget.edit_usage_requested.connect(self._edit_photo_usage)
        self._photos_widget.source_enabled_changed.connect(self._source_enabled_changed)
        self._photos_widget.edit_source_requested.connect(self._edit_source)
        self._photos_widget.delete_source_requested.connect(self._delete_source)
        self._photos_widget.source_policy_changed.connect(self._source_policy_changed)
        self._photos_widget.source_recursive_changed.connect(
            self._source_recursive_changed
        )
        self._photos_widget.open_photo_requested.connect(self._photo_editor.open_in_os)
        self._photo_editor.log_message.connect(self._photos_widget.log_view.appendPlainText)
        self._tabs.addTab(self._photos_widget, self._translator.tr("tab.photos"))

        # ----------------------------------------------------
        # Places and captions
        # ----------------------------------------------------

        self._photos_places_widget = PhotoPlacesWidget(
            translator=self._translator,
            save_location_override=self._save_photo_location_override,
            save_caption=self._save_photo_caption,
            save_locations=self._save_photo_editorial_locations,
            edit_source_photo=self._go_to_source_photo,
            parent=self,
            hover_preview=self._hover_photo_preview,
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

        self._album_settings_widget.set_photo_provider(self._project_service.list_album_photos)

        self._album_settings_widget.settings_changed.connect(self._save_album_settings)

        self._tabs.addTab(self._album_settings_widget, self._translator.tr('tab.album'))

        # The Plan's hover previews deliberately delegate to this very widget.
        # That guarantees identical composition/rendering and, importantly,
        # the exact same PreviewImageCache used by the Preview tab.
        self._album_preview_widget = AlbumPreviewWidget(
            self._template_registry,
            translator=self._translator,
            parent=self,
            render_service=self._preview_render_service,
        )

        self._album_plan_widget = AlbumPlanWidget(
            self._template_registry,
            translator=self._translator,
            parent=self,
            preview_widget=self._album_preview_widget,
        )
        self._album_plan_widget.settings_changed.connect(self._plan_settings_changed)

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

        # Raster keys track their own inputs; editorial text only needs
        # the album composition and widgets to be refreshed.
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
            self._translator.tr("main.project_file_filter"),
        )

        if not path:
            return

        project_path = Path(path)

        if project_path.suffix != ".photoalbum":
            project_path = project_path.with_suffix('.photoalbum')

        # Creating a project replaces the current one. Persist PDF preferences
        # before ProjectService closes the existing database.
        self._pdf_widget.save_project_settings()
        self._hover_photo_preview.clear()

        try:
            # QFileDialog already asked the user whether the
            # existing file may be replaced. Honour that choice.
            if self._project_service.is_open:
                self._project_service.close()

            if project_path.exists():
                project_path.unlink()

            self._project_service.create(project_path)

        except Exception as exc:
            self._show_error(self._translator.tr("main.create_project_error"))
            return

        self._scan_controller.reset()

        self._refresh_source_cards()

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
            self._translator.tr("main.project_file_filter"),
        )

        if not path:
            return

        self._open_project_path(Path(path))

    def _open_project_path(self, path: Path) -> None:
        """Open an existing project from an explicit path."""
        self._preview_render_service.clear()
        # ProjectService.open() closes the current project even when opening
        # the replacement subsequently fails.
        self._pdf_widget.save_project_settings()
        self._hover_photo_preview.clear()

        try:
            self._project_service.open(path)
        except Exception as exc:
            self._show_error(self._translator.tr("main.open_project_error"))
            return

        self._album_preview_widget.clear()
        self._load_project_settings()
        self._load_project_photos()
        self._update_project_state()

        project_path = self._project_service.project_path
        if project_path not in self._legacy_cache_workers:
            worker = LegacyCacheCleanupWorker(project_path)
            self._legacy_cache_workers[project_path] = worker
            worker.signals.finished.connect(self._legacy_cache_cleanup_finished)
            QThreadPool.globalInstance().start(worker)

        # The persisted snapshot is already visible. Necessary local analysis
        # or remote metadata resolution now continues in the background;
        # provider synchronization remains an explicit user action.
        if self._photos_widget.has_active_sources:
            self._scan_controller.start()

    @Slot(object, object)
    def _legacy_cache_cleanup_finished(self, project_path, result) -> None:
        self._legacy_cache_workers.pop(project_path, None)
        if result is None or project_path != self._project_service.project_path:
            return
        state, detail = result
        key = "cache.legacy_project_removed" if state == "removed" else "cache.legacy_project_cleanup_failed"
        self._photos_widget.log_view.appendPlainText(
            self._translator.tr(key, error=detail or "")
        )

    def _close_project(self) -> None:
        self._preview_render_service.clear()
        self._pdf_widget.save_project_settings()
        self._hover_photo_preview.clear()
        self._album_build_result = None
        self._project_service.close()

        self._scan_controller.reset()

        self._album_plan_widget.clear()
        self._album_preview_widget.clear()

        self._refresh_source_cards()
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
            source = self._project_service.add_local_source(Path(directory))
        except Exception as exc:
            self._show_error(self._translator.tr("main.add_local_source_error"))
            return

        self._refresh_source_cards()

        self._scan_controller.reset()

        self._update_project_state()

        # A newly added local folder only needs to refresh itself. Do not
        # re-run unrelated local or remote sources as a side effect.
        self._scan_controller.start(source.id)

    def _choose_synology_source(self, source_id: str | None = None) -> None:
        if not self._project_service.is_open:
            return
        current_source = self._project_service.get_photo_source(source_id) if source_id else None
        reconnecting = (
            current_source is not None
            and current_source.kind == "synology-photos"
        )
        dialog = SynologySourceDialog(
            self._translator,
            self,
            existing_source=current_source if reconnecting else None,
            edit_collection=reconnecting,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            if (current_source is not None
                    and dialog.source.collection_id == current_source.collection_id
                    and dialog.source.config.get("base_url") == current_source.config.get("base_url")):
                # Authentication/configuration is separate from refreshing an
                # unchanged collection: reconnect without replacing its snapshot.
                self._project_service.set_photo_source(dialog.source, dialog.provider)
                self._refresh_source_cards()
                self.statusBar().showMessage(
                    self._translator.tr("source.synology.session_attached"), 5000)
                # Reconnection restores the provider session, but a purged
                # cache still has to be repopulated. Synchronize this source
                # immediately so its snapshot/thumbnails become usable again.
                self._scan_controller.sync_source(dialog.source.id)
                return
            self._scan_controller.import_remote_source(dialog.source, dialog.provider)
        except Exception as exc:
            if dialog.provider is not None:
                try:
                    dialog.provider.close()
                except Exception:
                    pass
                dialog.provider = None
            self._show_error(self._translator.tr("main.configure_remote_source_error"))
            return

    def _source_import_completed(self) -> None:
        self._load_project_settings()
        self._update_project_state()

    def _refresh_source_cards(self) -> None:
        sources = self._project_service.list_sources() if self._project_service.is_open else []
        labels = self._project_service.source_labels() if sources else {}
        available = {source.id: self._project_service.available_metadata_candidates(source.id) for source in sources}
        sessions = {
            source.id: self._project_service.get_photo_source_session(source.id) is not None
            for source in sources
            if source.kind != "local"
        }
        statuses = {source.id: self._project_service.source_status(source) for source in sources}
        self._photos_widget.set_sources(sources, available, labels, sessions, statuses)
        self._photos_places_widget.set_source_labels(labels)

    def _source_enabled_changed(self, source_id, enabled) -> None:
        self._project_service.set_source_enabled(source_id, enabled)
        self._load_project_photos()
        self._update_project_state()
        if enabled:
            source = self._project_service.get_photo_source(source_id)
            if source.kind == "local" or self._project_service.get_photo_source_session(source_id) is not None:
                self._scan_controller.sync_source(source_id)
            else:
                self._photos_widget.log_view.appendPlainText(
                    self._translator.tr("sources.reactivated_snapshot", source=source.collection_name)
                )


    def _source_recursive_changed(self, source_id, recursive) -> None:
        from dataclasses import replace

        source = self._project_service.get_photo_source(source_id)
        if source is None or source.kind != "local":
            return

        recursive = bool(recursive)
        if bool(source.config.get("recursive", False)) == recursive:
            return

        config = dict(source.config)
        config["recursive"] = recursive
        self._project_service.set_photo_source(replace(source, config=config))
        self._refresh_source_cards()
        self._scan_controller.reset()
        self._update_project_state()
        self._scan_controller.start(source_id)

    def _source_policy_changed(self, source_id, policy) -> None:
        previous_policy = self._project_service.get_photo_metadata_policy(source_id)
        if (
            not previous_policy.nominatim_enabled
            and policy.nominatim_enabled
        ):
            # Once the first successful Nominatim refresh has populated the
            # geocoded locations, make Nominatim the default location source.
            # Wait for success so a failed/cancelled refresh never changes the
            # user's effective location policy.
            self._pending_nominatim_location_sources.add(source_id)
        elif not policy.nominatim_enabled:
            self._pending_nominatim_location_sources.discard(source_id)

        self._project_service.set_photo_metadata_policy(policy, source_id)
        self._project_service.apply_photo_metadata_policy(source_id=source_id)
        self._load_project_photos()
        if not self._scan_controller.is_running:
            self._scan_controller.refresh_metadata(source_id)

    def _metadata_refresh_finished(self, source_id, succeeded: bool) -> None:
        if source_id not in self._pending_nominatim_location_sources:
            return
        self._pending_nominatim_location_sources.discard(source_id)
        if not succeeded:
            return

        from dataclasses import replace

        policy = self._project_service.get_photo_metadata_policy(source_id)
        if not policy.nominatim_enabled:
            return
        if policy.location_preference != "geocoding":
            policy = replace(policy, location_preference="geocoding")
            self._project_service.set_photo_metadata_policy(policy, source_id)
            self._project_service.apply_photo_metadata_policy(source_id=source_id)

        # Rebuild the cards so the Lieu combo immediately reflects Nominatim,
        # and reload effective photo values without launching a second scan.
        self._load_project_photos()

    def _delete_source(self, source_id) -> None:
        source = self._project_service.get_photo_source(source_id)
        if source is None:
            return
        if QMessageBox.question(self, self._translator.tr("sources.delete"),
                self._translator.tr("sources.delete_confirm", name=source.collection_name)) != QMessageBox.StandardButton.Yes:
            return
        self._project_service.delete_source(source_id)
        self._load_project_photos()
        self._update_project_state()

    def _edit_source(self, source_id) -> None:
        from dataclasses import replace
        from PySide6.QtWidgets import QDialogButtonBox, QLineEdit, QVBoxLayout
        source = self._project_service.get_photo_source(source_id)
        if source is None:
            return
        if source.kind == "synology-photos":
            self._choose_synology_source(source_id)
            return
        if source.kind != "local":
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self._translator.tr("sources.modify"))
        layout = QVBoxLayout(dialog)
        path = QLineEdit(str(source.config["directory"]))
        layout.addWidget(path)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            directory = Path(path.text()).expanduser().resolve()
            config = dict(source.config)
            config["directory"] = str(directory)
            updated_source = replace(
                source,
                name=directory.name,
                collection_name=directory.name,
                config=config,
            )
            self._project_service.set_photo_source(updated_source)
            self._refresh_source_cards()
            self._scan_controller.reset()
            self._update_project_state()
            self._scan_controller.start(source_id)

    def _edit_photo_usage(self, photo) -> None:
        from photoalbum.gui.photo_usage_dialog import PhotoUsageDialog
        dialog = PhotoUsageDialog(photo, self._translator, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._project_service.set_photo_usage(photo.identity, dialog.usage())
            self._load_project_photos()
            self._photos_widget.select_photo(photo)
            self._update_project_state()

    def _load_project_settings(self) -> None:
        self._refresh_source_cards()

        album_settings = self._project_service.get_album_structure_settings()

        if album_settings is None:
            self._album_settings_widget.reset_to_defaults()
        else:
            self._album_settings_widget.set_settings(album_settings)

        project_name = self._project_service.get_project_name()
        pdf_settings = self._project_service.get_pdf_export_settings()
        if pdf_settings is None:
            pdf_settings = PdfExportSettings(
                metadata=ProjectPdfMetadata(title=project_name)
            )
            self._project_service.set_pdf_export_settings(pdf_settings)
        self._pdf_widget.set_project_settings(pdf_settings)

    def _set_scan_running(self, running: bool) -> None:
        self._new_project_action.setEnabled(not running)

        self._open_project_action.setEnabled(not running)

        self._close_project_action.setEnabled(not running and self._project_service.is_open)

        self._photos_widget.modify_source_button.setEnabled(
            not running and self._project_service.is_open
        )

        self._photos_widget.set_source_controls_enabled(not running)

        # Photos remains the project entry point. Every other
        # workflow tab is available as soon as the project contains
        # photos and no scan is currently running.
        photos_available = (
            self._project_service.is_open
            and not running
            and bool(self._project_service.list_album_photos())
        )

        # Photos is always available. It is the entry point
        # for creating/opening a project, selecting the source
        # folder and reading the analysis log.
        if self._tabs.count() > 0:
            self._tabs.setTabEnabled(0, True)

        for index in range(1, self._tabs.count()):
            self._tabs.setTabEnabled(index, photos_available)

        if running:
            self.statusBar().showMessage(self._translator.tr('main.analysis_in_progress'))
        else:
            # Do not let the persistent "analysis in progress" status survive
            # the end of a scan. Preserve any completion/error message emitted
            # just before running_changed(False), because those are transient and
            # should remain visible for their configured timeout.
            stale_statuses = {
                self._translator.tr('main.analysis_in_progress'),
                self._translator.tr('main.analysis_stopping'),
            }
            if self.statusBar().currentMessage() in stale_statuses:
                self.statusBar().clearMessage()

    def _rename_project(self) -> None:
        if not self._project_service.is_open:
            return

        current_name = self._project_service.get_project_name()
        name, accepted = QInputDialog.getText(
            self,
            self._translator.tr("main.rename_project"),
            self._translator.tr("main.project_name"),
            text=current_name,
        )
        if not accepted:
            return

        name = name.strip()
        if not name or name == current_name:
            return

        self._project_service.set_project_name(name)
        self._update_project_state()

    def _update_project_state(self) -> None:
        is_open = self._project_service.is_open
        self._close_project_action.setEnabled(is_open)
        self._photos_widget.modify_source_button.setEnabled(is_open)

        if is_open:
            project_path = self._project_service.project_path
            self._project_label.setText(self._project_service.get_project_name())
            self._project_filename_label.setText(project_path.name)
            self._project_filename_label.setVisible(True)
            self._project_rename_button.setVisible(True)
            self.statusBar().clearMessage()
        else:
            self._project_label.setText(self._translator.tr('main.no_project'))
            self._project_filename_label.clear()
            self._project_filename_label.setVisible(False)
            self._project_rename_button.setVisible(False)
            self._pdf_widget.set_project_settings(None)
            self.statusBar().clearMessage()

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
        self._album_settings_widget.set_available_photos(photos)

    def _prewarm_expensive_previews(self, result, settings, photos) -> None:
        """
        Pre-render expensive templates using exactly the same
        photo set as the album preview.

        The canonical pool also contains TEMPLATE_ONLY photos, even though
        they never appear in chronological photo pages.
        """

        page_format = settings.effective_page_format()

        project_photos = list(result.template_photos)

        instances = []

        # Covers.
        for cover in settings.covers.values():
            page = cover.page

            if self._preview_render_service.supports(page.template_id):
                instances.append(page)

        # Special-page instances.
        for item in result.pagination.pages:
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
                template_pack_settings=settings.template_pack_settings,
            )

    def _refresh_album_plan(self) -> None:
        if not self._project_service.is_open:
            self._album_plan_widget.clear()
            self._album_preview_widget.clear()
            return

        try:
            photos = self._project_service.list_album_photos()

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

            page_format = settings.effective_page_format()

            # Build the canonical Preview state first. Plan hover previews
            # delegate to it, including its already-warmed image cache.
            self._album_preview_widget.set_result(
                result,
                settings,
                page_format=page_format,
            )
            self._album_plan_widget.set_result(result, settings)

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
                self._translator.tr('main.build_plan_error', error=exc),
                7000,
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

    def _plan_settings_changed(self, settings) -> None:
        self._album_settings_widget.set_settings(settings)
        self._preview_render_service.clear()
        self._save_album_settings()

    def _save_photo_caption(self, photo: Photo, caption: str | None) -> None:
        try:
            self._project_service.set_photo_caption(photo.identity, caption)

            # Persist immediately, but defer the expensive album
            # rebuild until "Places and captions" is left.
            self._mark_editorial_album_dirty()
        except Exception as exc:
            self._show_error(self._translator.tr("main.save_photo_location_error"))

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
                    photo.identity,
                    components=components,
                    location_text=location_text,
                )
                changed = True
        except Exception as exc:
            self._show_error(self._translator.tr("main.save_photo_location_error"))
        finally:
            if changed:
                self._mark_editorial_album_dirty()

    def _save_photo_location_override(
        self,
        photo: Photo,
        components,
        location_text: str | None,
        manual_location_data: dict[str, object],
    ) -> None:
        try:
            self._project_service.set_editorial_location(
                photo.identity,
                components=components,
                location_text=location_text,
                manual_location_data_override=manual_location_data,
            )
            self._mark_editorial_album_dirty()
        except Exception as exc:
            self._show_error(self._translator.tr("main.save_photo_location_error"))

    def _show_transient_status(self, message: str) -> None:
        """Show scan results briefly; persistent details belong in the journal."""
        self.statusBar().showMessage(message, 5000)

    def _show_error(self, message: str) -> None:
        # A real asset request may have proved a provider session invalid.
        self._refresh_source_cards()
        QMessageBox.critical(self, APPLICATION_NAME, message)

    def _load_project_photos(self) -> None:
        if not self._project_service.is_open:
            self._photos_widget.model.clear()
            return

        photos = self._project_service.list_photos()

        selected = self._photos_widget.table.currentIndex().data(Qt.ItemDataRole.UserRole)
        self._refresh_source_cards()
        self._photos_widget.model.set_photos(photos)
        if isinstance(selected, Photo):
            self._photos_widget.select_photo(selected)
        album_photos = self._project_service.list_album_photos()
        self._photos_places_widget.set_photos(album_photos)
        self._update_album_years(album_photos)

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
        # Source refreshes can recreate cached image files at the same paths.
        # Expensive previews can key their raster cache from photo metadata,
        # so a blank raster produced while assets
        # were missing would otherwise survive the refresh.
        self._preview_render_service.clear()
        self._load_project_photos()
