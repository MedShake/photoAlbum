from datetime import datetime
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QDateTimeEdit, QLineEdit, QPushButton, QMessageBox,
)

from photoalbum.app import ProjectService
from photoalbum.export import PdfExportContent
from photoalbum.gui.main_window import MainWindow
from photoalbum.gui.photo_editor import PhotoEditor
from photoalbum.gui.scan_controller import ScanController
from photoalbum.gui.widgets.photo_sources_widget import PhotoSourcesWidget
from photoalbum.i18n import Translator
from photoalbum.models import (
    DateSource,
    GpsCandidate,
    GpsSource,
    LocationSource,
    MetadataCandidates,
    Photo,
)
from photoalbum.sources import (
    ProjectSource,
    SourceAsset,
    SourceCapabilities,
    SourceCollection,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait_until(app, predicate):
    deadline = monotonic() + 5
    while not predicate() and monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert predicate()


@pytest.fixture
def window(app, monkeypatch):
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Cancel)
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: None)
    window = MainWindow()
    yield window
    wait_until(app, lambda: not window._scan_controller.is_running and not window._pdf_widget.is_running)
    window.close()
    window.deleteLater()
    app.processEvents()


def test_window_wires_six_tabs_and_status_bar(window):
    assert window._tabs.count() == 6
    assert window._tabs.widget(0) is window._photos_widget
    assert window._tabs.widget(5) is window._pdf_widget
    window._pdf_widget.status_message.emit('Export complete', 1000)
    assert window.statusBar().currentMessage() == 'Export complete'
    window._scan_controller.status_message.emit('Scanning')
    assert window.statusBar().currentMessage() == 'Scanning'


def test_project_without_album_settings_uses_msb_and_existing_settings_survive(window, tmp_path):
    import json
    from photoalbum.album import CoverPosition, CoverSettings, album_settings_to_json

    service = window._project_service
    project = tmp_path / 'defaults.photoalbum'
    service.create(project)
    assert service.get_album_structure_settings() is None
    window._load_project_settings()
    settings = window._album_settings_widget.settings()
    assert settings.covers[CoverPosition.FRONT].template_id == 'year-photo-scatter'
    assert settings.photo_pages.automatic_mode.mode_id == 'msb-orientation-1-2-3'
    assert settings.year_dividers.template_id == 'calendar-index'
    settings.covers[CoverPosition.FRONT] = CoverSettings(
        position=CoverPosition.FRONT, template_id='simplex-full-photo-cover',
    )
    saved = json.loads(album_settings_to_json(settings))
    saved.pop('template_pack_settings')
    service._database.set_project_metadata(service.ALBUM_STRUCTURE_SETTINGS_KEY, json.dumps(saved))
    service.close()
    service.open(project)
    window._load_project_settings()
    assert window._album_settings_widget.settings() == settings


def test_custom_dimensions_apply_persist_and_rebuild_once(window, tmp_path, monkeypatch):
    service = window._project_service
    project = tmp_path / "custom.photoalbum"
    service.create(project)
    widget = window._album_settings_widget
    window._tabs.setTabEnabled(window._tabs.indexOf(widget), True)
    widget._page_format_combo.setCurrentIndex(widget._page_format_combo.findData("custom"))
    build = Mock(wraps=window._album_builder.build)
    persist = Mock(wraps=service.set_album_structure_settings)
    preview = Mock()
    monkeypatch.setattr(window._album_builder, "build", build)
    monkeypatch.setattr(service, "set_album_structure_settings", persist)
    monkeypatch.setattr(window._album_preview_widget, "set_result", preview)
    widget._custom_width_spin.setValue(345.5)
    widget._custom_height_spin.setValue(123.25)
    build.assert_not_called()
    persist.assert_not_called()
    widget._custom_apply_button.click()
    assert build.call_count == persist.call_count == preview.call_count == 1
    page = preview.call_args.kwargs["page_format"]
    assert (page.width_mm, page.height_mm) == (345.5, 123.25)
    reopened = ProjectService()
    reopened.open(project)
    assert reopened.get_album_structure_settings() == widget.settings()
    reopened.close()


def test_format_and_orientation_persist_and_rebuild_once(window, tmp_path, monkeypatch):
    from photoalbum.album import oriented_page_format, page_format_from_id

    service = window._project_service
    service.create(tmp_path / "orientation.photoalbum")
    widget = window._album_settings_widget
    widget.set_settings(widget.settings())
    persist = Mock(wraps=service.set_album_structure_settings)
    build = Mock(wraps=window._album_builder.build)
    plan, preview, prewarm = Mock(), Mock(), Mock()
    monkeypatch.setattr(service, "set_album_structure_settings", persist)
    monkeypatch.setattr(window._album_builder, "build", build)
    monkeypatch.setattr(window._album_plan_widget, "set_result", plan)
    monkeypatch.setattr(window._album_preview_widget, "set_result", preview)
    monkeypatch.setattr(window, "_prewarm_expensive_previews", prewarm)
    for combo, value in [
        (widget._orientation_combo, "landscape"),
        (widget._page_format_combo, "us-letter"),
        (widget._page_format_combo, "a4"),
        (widget._orientation_combo, "portrait"),
    ]:
        for spy in (persist, build, plan, preview, prewarm):
            spy.reset_mock()
        combo.setCurrentIndex(combo.findData(value))
        for spy in (persist, build, plan, preview, prewarm):
            assert spy.call_count == 1
        settings = widget.settings()
        assert service.get_album_structure_settings() == settings
        assert preview.call_args.kwargs["page_format"] == oriented_page_format(
            page_format_from_id(settings.page_format), settings.orientation,
        )


def test_photo_controls_forward_signals_and_selection_respects_sort(app, tmp_path):
    view = PhotoSourcesWidget(Translator('en'))
    source, recursive = Mock(), Mock()
    view.source_requested.connect(source)
    view.source_enabled_changed.connect(recursive)
    view.source_requested.emit()
    view.source_enabled_changed.emit("source-a", True)
    source.assert_called_once_with()
    recursive.assert_called_once_with("source-a", True)
    first = Photo(path=tmp_path / 'a.jpg', filename='a.jpg')
    second = Photo(path=tmp_path / 'z.jpg', filename='z.jpg')
    view.model.set_photos([first, second])
    view.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
    view.select_photo(first)
    selected = view.proxy_model.mapToSource(view.table.currentIndex())
    assert view.model.photo_at(selected.row()).path == first.path
    view.close()


def test_photo_table_keeps_hover_features_without_visual_selection(app, tmp_path):
    view = PhotoSourcesWidget(Translator('en'))
    first = Photo(path=tmp_path / 'a.jpg', filename='a.jpg')
    second = Photo(path=tmp_path / 'b.jpg', filename='b.jpg')
    view.model.set_photos([first, second])

    assert view.table.selectionMode() == QAbstractItemView.SelectionMode.NoSelection
    assert view.table.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert view.table.alternatingRowColors()
    assert view.table.hasMouseTracking()

    view.select_photo(second)
    assert view.table.currentIndex().data(Qt.ItemDataRole.UserRole).identity == second.identity
    assert not view.table.selectionModel().selectedIndexes()
    view.close()


def test_hover_preview_clears_on_model_reset_and_tab_hide(app, tmp_path):
    path = tmp_path / 'photo.jpg'
    Image.new('RGB', (100, 80), 'red').save(path)
    view = PhotoSourcesWidget(Translator('en'))
    view.model.set_photos([Photo(path=path, filename=path.name)])
    view.show()
    view._source_preview_row = 0
    view._schedule_source_photo_preview()
    wait_until(app, lambda: view._hover_preview._preview is not None)
    view.model.clear()
    assert view._hover_preview._preview is None
    assert view._source_preview_row is None
    view.model.set_photos([Photo(path=path, filename=path.name)])
    view._source_preview_row = 0
    view._schedule_source_photo_preview()
    assert view._hover_preview._timer.isActive()
    view.hide()
    assert not view._hover_preview._timer.isActive()
    view.close()


def test_main_window_shares_only_the_hover_preview_cache(window):
    assert window._photos_widget._hover_preview is window._hover_photo_preview
    assert window._photos_places_widget._hover_preview is window._hover_photo_preview
    assert window._hover_photo_preview._cache is window._hover_preview_cache
    assert (
        window._hover_preview_cache
        is not window._album_preview_widget._thumbnail_cache
    )


@pytest.mark.parametrize('action', ['save', 'restore', 'cancel'])
def test_date_editor_preserves_save_restore_and_cancel(app, monkeypatch, tmp_path, action):
    service = Mock()
    editor = PhotoEditor(service, Translator('en'), language='en')
    changed = Mock()
    editor.photos_changed.connect(changed)
    original = datetime(2020, 1, 2, 12, 0)
    replacement = datetime(2025, 3, 4, 15, 30)
    photo = Photo(path=tmp_path / 'photo.jpg', filename='photo.jpg',
                  capture_datetime=datetime(2024, 1, 1), original_capture_datetime=original)

    def execute(dialog):
        if action == 'restore':
            next(b for b in dialog.findChildren(QPushButton) if 'Restore' in b.text()).click()
        elif action == 'save':
            dialog.findChild(QDateTimeEdit).setDateTime(replacement)
        return QDialog.DialogCode.Rejected if action == 'cancel' else QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, 'exec', execute)
    editor.edit_datetime(photo)
    if action == 'save':
        service.set_manual_capture_datetime.assert_called_once_with(photo.identity, replacement)
    elif action == 'restore':
        service.restore_original_capture_datetime.assert_called_once_with(photo.identity)
    else:
        service.set_manual_capture_datetime.assert_not_called()
        service.restore_original_capture_datetime.assert_not_called()
    assert changed.call_count == (0 if action == 'cancel' else 1)


@pytest.mark.parametrize('restore', [False, True])
def test_gps_editor_preserves_coordinates_and_requests_geocoding(app, monkeypatch, tmp_path, restore):
    service = Mock()
    editor = PhotoEditor(service, Translator('en'), language='en')
    editor._start_gps_geocoding = Mock()
    photo = Photo(path=tmp_path / 'photo.jpg', filename='photo.jpg',
                  latitude=10, longitude=20, original_latitude=30, original_longitude=40)

    def execute(dialog):
        if restore:
            next(b for b in dialog.findChildren(QPushButton) if 'Restore' in b.text()).click()
        else:
            latitude, longitude = dialog.findChildren(QLineEdit)
            latitude.setText("-12,3456789")
            longitude.setText("78.1234567")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, 'exec', execute)
    editor.edit_gps(photo)
    if restore:
        service.restore_original_gps.assert_called_once_with(photo.identity)
        editor._start_gps_geocoding.assert_called_once_with(photo.identity, 30, 40)
    else:
        service.set_manual_gps.assert_called_once_with(photo.identity, -12.3456789, 78.1234567)
        editor._start_gps_geocoding.assert_called_once_with(photo.identity, -12.3456789, 78.1234567)


def test_gps_editor_shows_empty_fields_without_gps(
    app, monkeypatch, tmp_path,
):
    service = Mock()
    editor = PhotoEditor(service, Translator('en'), language='en')
    editor._start_gps_geocoding = Mock()
    photo = Photo(
        path=tmp_path / 'photo.jpg',
        filename='photo.jpg',
    )

    def execute(dialog):
        latitude, longitude = dialog.findChildren(QLineEdit)
        assert latitude.text() == ''
        assert longitude.text() == ''
        assert not any(
            'Restore' in button.text()
            for button in dialog.findChildren(QPushButton)
        )
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, 'exec', execute)

    editor.edit_gps(photo)

    service.set_manual_gps.assert_not_called()
    editor._start_gps_geocoding.assert_not_called()


def test_gps_editor_invalid_coordinates_do_not_accept_dialog(
    app, monkeypatch, tmp_path,
):
    service = Mock()
    editor = PhotoEditor(service, Translator('en'), language='en')
    photo = Photo(
        path=tmp_path / 'photo.jpg',
        filename='photo.jpg',
    )

    warning = Mock()
    monkeypatch.setattr(QMessageBox, 'warning', warning)

    def execute(dialog):
        latitude, longitude = dialog.findChildren(QLineEdit)
        latitude.setText("48.123")
        longitude.clear()

        save_button = next(
            button
            for button in dialog.findChildren(QPushButton)
            if button.text() == "Save"
        )
        save_button.click()
        app.processEvents()

        assert dialog.result() != QDialog.DialogCode.Accepted
        assert warning.call_count == 1

        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, 'exec', execute)

    editor.edit_gps(photo)

    service.set_manual_gps.assert_not_called()


def test_gps_editor_can_clear_effective_coordinates(
    app, monkeypatch, tmp_path,
):
    service = Mock()
    editor = PhotoEditor(service, Translator('en'), language='en')
    editor._start_gps_geocoding = Mock()
    photo = Photo(
        path=tmp_path / 'photo.jpg',
        filename='photo.jpg',
        latitude=10,
        longitude=20,
        original_latitude=30,
        original_longitude=40,
    )

    def execute(dialog):
        latitude, longitude = dialog.findChildren(QLineEdit)
        latitude.clear()
        longitude.clear()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, 'exec', execute)

    editor.edit_gps(photo)

    service.set_manual_gps.assert_called_once_with(
        photo.identity,
        None,
        None,
    )
    editor._start_gps_geocoding.assert_not_called()


def test_scan_updates_project_and_derived_views(window, app, tmp_path):
    source = tmp_path / 'photos'
    source.mkdir()
    Image.new('RGB', (100, 80), 'red').save(source / '2025-01-02.jpg')
    window._project_service.create(tmp_path / 'project.photoalbum')
    window._project_service.set_source_directory(source)
    window._load_project_settings()
    window._scan_controller.start()
    assert window._scan_controller.is_running
    assert not window._open_project_action.isEnabled()
    wait_until(app, lambda: not window._scan_controller.is_running)
    assert window._photos_widget.model.rowCount() == 1
    assert len(window._project_service.list_photos()) == 1
    assert window._scan_controller.analysis_completed
    assert window._open_project_action.isEnabled()
    assert window._tabs.isTabEnabled(1)
    window._close_project()
    assert window._photos_widget.model.rowCount() == 0
    assert not window._scan_controller.analysis_completed


def test_scan_without_project_reports_error(app):
    service = ProjectService()
    view = PhotoSourcesWidget(Translator('en'))
    controller = ScanController(service, view, Translator('en'), language='en')
    errors = []
    controller.error.connect(errors.append)
    controller.start()
    assert len(errors) == 1
    assert not controller.is_running
    view.close()


def test_remote_import_and_sync_are_async_and_analysis_does_not_sync_provider(
    app,
    tmp_path,
):
    class Provider:
        kind = "future-provider"
        label = "Future Photos"
        capabilities = SourceCapabilities(
            date_candidates=frozenset({"provider"}),
            can_fetch_original=True,
        )

        def __init__(self):
            self.list_calls = 0

        def list_assets(self, collection_id):
            self.list_calls += 1
            return [SourceAsset(id="1", filename="photo.jpg")]

        def fetch_thumbnail(self, asset, destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"thumbnail")
            return destination

        def fetch_original(self, asset, destination):
            raise AssertionError("Original must not be fetched during import")

        def close(self):
            pass

    service = ProjectService()
    service.create(tmp_path / "async.photoalbum")
    source = ProjectSource(
        id="future-1",
        kind="future-provider",
        name="remote",
        collection_id="album",
        collection_name="Album",
        provider_label="Future Photos",
        capabilities=Provider.capabilities,
    )
    provider = Provider()
    view = PhotoSourcesWidget(Translator("en"))
    controller = ScanController(service, view, Translator("en"), language="en")

    controller.import_remote_source(source, provider)
    assert controller.is_running
    assert view.source_progress_bar.maximum() == 0
    wait_until(app, lambda: not controller.is_running)
    assert provider.list_calls == 1
    assert service.get_photo_source() == source

    controller.start()
    assert controller.is_running
    wait_until(app, lambda: not controller.is_running)
    assert provider.list_calls == 1

    controller.sync_source("future-1")
    assert controller.is_running
    wait_until(app, lambda: not controller.is_running)
    assert provider.list_calls == 2
    service.close()
    view.close()


def test_remote_sync_requires_an_attached_session_before_starting(app, tmp_path):
    service = ProjectService()
    service.create(tmp_path / "remote-disconnected.photoalbum")
    source = ProjectSource(
        id="remote-1",
        kind="future-provider",
        name="remote",
        collection_id="album",
        collection_name="Album",
        provider_label="Future Photos",
    )
    service.set_photo_source(source)
    view = PhotoSourcesWidget(Translator("en"))
    controller = ScanController(service, view, Translator("en"), language="en")
    errors = []
    controller.error.connect(errors.append)

    controller.sync_source()

    assert not controller.is_running
    assert errors == [Translator("en").tr("sources.reconnect_required")]
    service.close()
    view.close()


def test_open_remote_project_exposes_snapshot_before_background_refresh(
    window,
    tmp_path,
):
    from photoalbum.database import PhotoRepository, ProjectDatabase

    project_path = tmp_path / "snapshot.photoalbum"
    database = ProjectDatabase(project_path)
    database.initialize()
    source = ProjectSource(
        id="remote-1",
        kind="future-provider",
        name="remote",
        collection_id="album",
        collection_name="Album",
        provider_label="Future Photos",
    )
    from photoalbum.database.source_repository import SourceRepository
    SourceRepository(database).save(source)
    PhotoRepository(database).save(
        Photo(
            path=tmp_path / "thumbnail.jpg",
            filename="photo.jpg",
            source_id="remote-1",
            asset_id="1",
        )
    )
    database.close()

    window._open_project_path(project_path)

    assert window._photos_widget.model.rowCount() == 1
    assert window._photos_widget._sources == [source]


def test_pdf_document_summary_uses_effective_dimensions_without_orientation(window):
    from dataclasses import replace
    from photoalbum.album import PageOrientation

    widget = window._pdf_widget
    base = window._album_settings_widget.settings()

    window._album_settings_widget.set_settings(replace(
        base, page_format="a4", orientation=PageOrientation.PORTRAIT,
    ))
    widget.update_summary()
    assert widget._pdf_format_label.text() == "A4 — 210 × 297 mm"
    assert not hasattr(widget, "_pdf_orientation_label")

    window._album_settings_widget.set_settings(replace(
        window._album_settings_widget.settings(),
        page_format="a4", orientation=PageOrientation.LANDSCAPE,
    ))
    widget.update_summary()
    assert widget._pdf_format_label.text() == "A4 — 297 × 210 mm"

    window._album_settings_widget.set_settings(replace(
        window._album_settings_widget.settings(),
        page_format="custom", custom_width_mm=180.0, custom_height_mm=180.0,
    ))
    widget.update_summary()
    assert widget._pdf_format_label.text() == "Custom — 180 × 180 mm"


@pytest.mark.parametrize('failure', [False, True])
@pytest.mark.parametrize('orientation', ['portrait', 'landscape', 'custom'])
def test_pdf_worker_completes_or_fails_and_reenables_controls(window, app, tmp_path, monkeypatch, failure, orientation):
    from dataclasses import replace
    from photoalbum.album import PageOrientation
    from photoalbum.gui.widgets import pdf_export_widget as module
    received = []

    class ExportService:
        def __init__(self, translator):
            pass

        def export(self, **kwargs):
            received.append(kwargs)
            if failure:
                raise RuntimeError('test export failure')
            kwargs['progress_callback'](4, 4, 'Done')

    monkeypatch.setattr(module, 'PdfExportService', ExportService)
    window._project_service.create(tmp_path / 'project.photoalbum')
    window._album_settings_widget.set_settings(replace(
        window._album_settings_widget.settings(),
        orientation=PageOrientation.LANDSCAPE if orientation == 'custom' else PageOrientation(orientation),
        page_format='custom' if orientation == 'custom' else 'a4',
        custom_width_mm=345.5, custom_height_mm=123.25,
    ))
    window._album_build_result = SimpleNamespace(pagination=SimpleNamespace(pages=[object()]), total_page_count=5, template_photos=())
    widget = window._pdf_widget
    window._tabs.setTabEnabled(5, True)
    widget._pdf_output_edit.setText(str(tmp_path / 'album'))
    widget._pdf_title_edit.setText('Test title')
    widget._pdf_content_covers_radio.setChecked(True)
    widget._pdf_dpi_combo.setCurrentIndex(0)
    prepared = []
    widget._before_export = lambda: prepared.append(True)
    widget.generate()
    assert widget.is_running
    assert not widget.generate_button.isEnabled()
    wait_until(app, lambda: not widget.is_running)
    assert widget.generate_button.isEnabled()
    assert widget._pdf_output_button.isEnabled()
    assert widget._pdf_dpi_combo.isEnabled()
    assert prepared == [True]
    assert received[0]['content'] == PdfExportContent.COVERS
    assert received[0]['metadata'].title == 'Test title'
    assert received[0]['dpi'] == 96
    assert (received[0]['page_width_mm'], received[0]['page_height_mm']) == (
        (345.5, 123.25) if orientation == 'custom' else
        (297.0, 210.0) if orientation == 'landscape' else (210.0, 297.0)
    )
    assert received[0]['output_path'].suffix == '.pdf'

    log = widget._pdf_log_view.toPlainText()
    assert 'PDF generation' in log
    assert 'Starting rendering engine…' in log

    if failure:
        assert 'ERROR: Could not generate the PDF.' in log
    else:
        assert 'PDF created successfully.' in log
        assert widget._pdf_progress_bar.value() == 4
        assert 'album.pdf' in window.statusBar().currentMessage()


def test_scan_cancellation_keeps_partial_results(app, tmp_path):
    from photoalbum.scanner import LibraryScanResult

    view = PhotoSourcesWidget(Translator('en'))
    controller = ScanController(ProjectService(), view, Translator('en'), language='en')
    worker = Mock()
    controller._scan_worker = worker
    controller.cancel()
    worker.request_cancel.assert_called_once_with()
    received = []
    controller.photos_ready.connect(received.append)
    photo = Photo(path=tmp_path / 'partial.jpg', filename='partial.jpg')
    controller._scan_completed(LibraryScanResult(photos=[photo], cancelled=True))
    assert received == [[photo]]
    assert not controller.analysis_completed
    assert view.summary_label.text().startswith(Translator('en').tr('main.analysis_cancelled'))
    view.close()


def test_geocoding_worker_updates_photo_and_releases_thread(app, monkeypatch, tmp_path):
    from PySide6.QtCore import QObject, Signal, Slot
    from photoalbum.gui import photo_editor as module

    location = SimpleNamespace(place_name='Place', city='Paris', address='Address', raw_data={})

    class Worker(QObject):
        completed = Signal(object)
        failed = Signal(str)

        def __init__(self, **kwargs):
            super().__init__()

        @Slot()
        def run(self):
            self.completed.emit(location)

    monkeypatch.setattr(module, 'GpsGeocodingWorker', Worker)
    service = Mock()
    service.project_path = tmp_path / 'project.photoalbum'
    editor = PhotoEditor(service, Translator('en'), language='en')
    changed = Mock()
    editor.photos_changed.connect(changed)
    editor._start_gps_geocoding(tmp_path / 'photo.jpg', 48.0, 2.0)
    assert editor.is_running
    wait_until(app, lambda: not editor.is_running)
    service.set_geocoded_location.assert_called_once_with(
        tmp_path / 'photo.jpg', place_name='Place', city='Paris', address='Address', raw_location_data={},
    )
    changed.assert_called_once_with()
    assert editor._gps_worker is None


def test_window_refuses_close_during_export(window):
    from PySide6.QtGui import QCloseEvent

    window._pdf_widget._pdf_thread = object()
    try:
        event = QCloseEvent()
        window.closeEvent(event)
        assert not event.isAccepted()
    finally:
        window._pdf_widget._pdf_thread = None


def test_photo_sources_widget_displays_scan_phase_progress(app):
    view = PhotoSourcesWidget(Translator("en"))

    view.prepare_scan_progress(nominatim_enabled=True)

    assert view.metadata_progress_label.isVisible() is False
    assert view.nominatim_progress_label.isVisible() is False

    # Visibility of a child follows the top-level widget, so show it
    # before asserting the actual presentation state.
    view.show()
    app.processEvents()

    assert view.metadata_progress_label.isVisible()
    assert view.metadata_progress_bar.isVisible()
    assert view.nominatim_progress_label.isVisible()
    assert view.nominatim_progress_bar.isVisible()

    view.update_scan_phase_progress(
        "metadata",
        12,
        20,
    )
    view.update_scan_phase_progress(
        "nominatim",
        3,
        7,
    )

    assert view.metadata_progress_bar.maximum() == 20
    assert view.metadata_progress_bar.value() == 12
    assert view.metadata_progress_bar.format() == "12 / 20"

    assert view.nominatim_progress_bar.maximum() == 7
    assert view.nominatim_progress_bar.value() == 3
    assert view.nominatim_progress_bar.format() == "3 / 7"


def test_photo_sources_widget_hides_nominatim_when_disabled(app):
    view = PhotoSourcesWidget(Translator("en"))
    view.show()
    app.processEvents()

    view.prepare_scan_progress(nominatim_enabled=False)

    assert view.metadata_progress_label.isVisible()
    assert view.metadata_progress_bar.isVisible()
    assert not view.nominatim_progress_label.isVisible()
    assert not view.nominatim_progress_bar.isVisible()


def _source_card(view, *, label="Synology Photos", kind="synology-photos",
                 available=None, policy=None, session_available=False):
    source = ProjectSource(
        id="source-a", kind=kind, name="NAS", collection_id="album",
        collection_name="Album", provider_label=label, metadata_policy=policy,
    )
    view.set_sources([source], {source.id: available or {
        "date": {"provider", "exif", "filename"}, "gps": {"provider", "exif"},
        "location": {"provider", "geocoding"}, "caption": {"provider"},
    }}, {source.id: label}, {source.id: session_available})
    return view._source_cards.itemAt(0).widget()


def test_photo_sources_widget_metadata_policy_controls(app):
    from photoalbum.sources import PhotoMetadataPolicy
    view = PhotoSourcesWidget(Translator("en"))
    received = []
    view.source_policy_changed.connect(lambda sid, policy: received.append((sid, policy)))
    card = _source_card(view, policy=PhotoMetadataPolicy(
        date_preference="source", gps_preference="exif",
        location_preference="source", nominatim_enabled=False,
    ))
    assert card._combos["date"].currentData() == "source"
    assert card._combos["gps"].currentData() == "exif"
    assert card._combos["location"].currentData() == "source"
    assert not card._nominatim.isChecked()
    assert received == []
    card._nominatim.setChecked(True)
    assert received[-1] == ("source-a", PhotoMetadataPolicy(
        date_preference="source", gps_preference="exif",
        location_preference="source", nominatim_enabled=True,
    ))
    view.close()


def test_policy_choices_use_actual_candidates_and_provider_label(app):
    view = PhotoSourcesWidget(Translator("en"))
    card = _source_card(view, available={
        "date": {"provider", "filename"}, "gps": {"provider"},
        "location": {"provider", "geocoding"}, "caption": {"provider"},
    })
    date, gps = card._combos["date"], card._combos["gps"]
    assert [date.itemText(i) for i in range(date.count())] == ["Synology Photos", "Filename"]
    assert date.findData("exif") == -1
    assert [gps.itemText(i) for i in range(gps.count())] == ["Synology Photos"]
    assert card.sync_button.text() == "Synchronize"
    view.close()


def test_remote_source_card_exposes_reconnect_action_without_heartbeat(app):
    view = PhotoSourcesWidget(Translator("en"))
    disconnected = _source_card(view, session_available=False)
    assert disconnected.connection_status_label.text() == "Reconnection required"
    assert disconnected.edit_button.text() == "Reconnect…"
    assert not disconnected.sync_button.isEnabled()

    connected = _source_card(view, session_available=True)
    assert not connected.connection_status_label.isVisible()
    assert connected.edit_button.text() == "Modify…"
    assert connected.sync_button.isEnabled()
    view.close()


def test_each_source_card_exposes_its_own_sync_action(app):
    view = PhotoSourcesWidget(Translator("en"))
    local = _source_card(view, label="Local folder", kind="local")
    received = []
    view.source_sync_requested.connect(received.append)

    assert local.sync_button.text() == "Synchronize"
    assert local.sync_button.isEnabled()
    assert local.sync_button.width() == local.edit_button.width()
    local.sync_button.click()
    assert received == ["source-a"]
    assert not hasattr(view, "analyze_button")
    assert not hasattr(view, "sync_button")
    view.close()


def test_provider_label_mechanism_accepts_immich_without_special_ui_code(app):
    view = PhotoSourcesWidget(Translator("en"))
    card = _source_card(view, label="Immich", kind="immich")
    assert card._combos["date"].itemText(0) == "Immich"
    assert card._combos["location"].itemText(0) == "Immich"
    view.close()


def test_table_displays_effective_provider_provenance(app, tmp_path):
    view = PhotoSourcesWidget(Translator("en"))
    _source_card(view)
    view.model.set_photos([
        Photo(
            path=tmp_path / "photo.jpg", filename="photo.jpg", source_id="source-a",
            capture_datetime=datetime(2024, 1, 1), date_source=DateSource.SOURCE,
            latitude=48.0, longitude=2.0, gps_source=GpsSource.SOURCE,
            city="Paris", location_source=LocationSource.SOURCE,
        )
    ])
    assert view.model.index(0, 3).data() == "Synology Photos"
    assert view.model.index(0, 4).data() == "Yes — Synology Photos"
    assert view.model.index(0, 6).data() == "Synology Photos"
    view.close()


def test_main_window_persists_photo_metadata_policy(window, tmp_path):
    from photoalbum.sources import PhotoMetadataPolicy
    service = window._project_service
    service.create(tmp_path / "policy-ui.photoalbum")
    service.set_source_directory(tmp_path / "photos")
    window._load_project_settings()
    policy = PhotoMetadataPolicy(
        date_preference="filename", gps_preference="exif",
        location_preference="none", nominatim_enabled=False,
    )
    window._source_policy_changed(service.get_photo_source().id, policy)
    assert service.get_photo_metadata_policy() == policy


def test_policy_change_immediately_refreshes_all_effective_values_and_sources(
    window, app, tmp_path,
):
    from photoalbum.database import PhotoRepository
    from photoalbum.sources import PhotoMetadataPolicy
    service = window._project_service
    service.create(tmp_path / "immediate-policy.photoalbum")
    service.set_source_directory(tmp_path / "photos")
    path = tmp_path / "photo.jpg"
    PhotoRepository(service._require_database()).save(
        Photo(
            path=path, filename=path.name, source_id=service.get_photo_source().id,
            asset_id=str(path), capture_datetime=datetime(2020, 1, 1),
            date_source=DateSource.EXIF, latitude=47.0, longitude=-1.0,
            gps_source=GpsSource.EXIF, exif_capture_datetime=datetime(2020, 1, 1),
            source_capture_datetime=datetime(2024, 7, 1),
            exif_latitude=47.0, exif_longitude=-1.0,
            source_latitude=48.0, source_longitude=2.0,
            source_location_data={"city": "Paris", "address": "Paris"},
        )
    )
    window._load_project_settings()
    window._load_project_photos()
    window._source_policy_changed(service.get_photo_source().id, PhotoMetadataPolicy(
        date_preference="source", gps_preference="source",
        location_preference="source", nominatim_enabled=False,
    ))
    displayed = window._photos_widget.model.photo_at(0)
    assert displayed.capture_datetime == datetime(2024, 7, 1)
    assert displayed.date_source == DateSource.SOURCE
    assert (displayed.latitude, displayed.longitude) == (48.0, 2.0)
    assert displayed.gps_source == GpsSource.SOURCE
    assert displayed.city == "Paris"
    assert displayed.location_source == LocationSource.SOURCE
    wait_until(app, lambda: not window._scan_controller.is_running)


def test_photo_sources_widget_uses_user_facing_source_and_policy_labels(app):
    from PySide6.QtWidgets import QGroupBox
    view = PhotoSourcesWidget(Translator("fr"))
    card = _source_card(view)
    titles = {group.title() for group in view.findChildren(QGroupBox)}
    assert "Ajouter une source" in titles
    assert "Source(s) de l’album" not in titles
    assert "Actualisation des photos" not in titles
    assert card.title() == "Synology Photos — Album"
    assert not hasattr(view, "_sources_scroll")
    assert not view.summary_label.isVisible()
    assert view.modify_source_button.text() == "Ajouter…"
    assert "OpenStreetMap" in card._nominatim.toolTip()
    assert "Internet" in card._nominatim.toolTip()
    view.close()


def test_source_metadata_provenance_translations_are_not_raw_keys():
    english = Translator("en")
    french = Translator("fr")

    assert english.tr("photos.date_source.source") == "Photo source"
    assert english.tr("photos.location_source.source") == "Photo source"

    assert french.tr("photos.date_source.source") == "Source des photos"
    assert french.tr("photos.location_source.source") == "Source des photos"


def test_photo_sources_widget_displays_source_sync_progress(app):
    view = PhotoSourcesWidget(Translator("en"))
    view.show()
    app.processEvents()

    view.prepare_source_progress()

    assert view.source_progress_label.isVisible()
    assert view.source_progress_bar.isVisible()
    assert not view.metadata_progress_label.isVisible()
    assert not view.nominatim_progress_label.isVisible()

    # Unknown total while the provider is listing its collection.
    assert view.source_progress_bar.minimum() == 0
    assert view.source_progress_bar.maximum() == 0

    view.update_source_progress(83, 171)

    assert view.source_progress_bar.maximum() == 171
    assert view.source_progress_bar.value() == 83
    assert view.source_progress_bar.format() == "83 / 171"

    view.finish_processing_progress()

    assert not view.source_progress_bar.isVisible()
    assert not view.metadata_progress_bar.isVisible()
    assert not view.nominatim_progress_bar.isVisible()

    view.close()


def test_project_header_shows_name_edit_action_and_filename(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    project = tmp_path / "technical-name.photoalbum"
    window._project_service.create(project)
    window._load_project_settings()
    window._update_project_state()

    assert window._project_label.text() == "technical-name"
    assert window._project_filename_label.text() == "technical-name.photoalbum"
    assert window._project_filename_label.isVisibleTo(window)
    assert window._project_rename_button.isVisibleTo(window)

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Nantes 2026", True),
    )
    window._rename_project()

    assert window._project_label.text() == "Nantes 2026"
    assert window._project_filename_label.text() == "technical-name.photoalbum"
    assert window._project_service.get_project_name() == "Nantes 2026"


def test_pdf_failure_popup_surfaces_actionable_worker_message(window):
    errors = []
    window._pdf_widget.error.connect(errors.append)
    message = "Reconnect the source containing ‘photo.jpg’ before generating the PDF."

    window._pdf_widget._pdf_export_failed(message)

    assert errors[-1] == message
    assert message in window._pdf_widget._pdf_log_view.toPlainText()


def test_pdf_preferences_load_persist_and_keep_project_title_independent(window, tmp_path):
    project = tmp_path / "nantes.photoalbum"
    window._project_service.create(project)
    window._load_project_settings()

    pdf = window._pdf_widget
    assert pdf._pdf_title_edit.text() == "nantes"
    assert pdf._pdf_dpi_combo.currentData() == 300
    assert pdf._pdf_content_complete_radio.isChecked()

    pdf._pdf_title_edit.setText("Nantes — album photo")
    pdf._pdf_title_edit.editingFinished.emit()
    pdf._pdf_dpi_combo.setCurrentIndex(pdf._pdf_dpi_combo.findData(600))
    pdf._pdf_content_body_radio.setChecked(True)

    stored = window._project_service.get_pdf_export_settings()
    assert stored.metadata.title == "Nantes — album photo"
    assert stored.dpi == 600
    assert stored.content == "body"

    window._project_service.set_project_name("Voyage à Nantes")
    window._load_project_settings()
    assert pdf._pdf_title_edit.text() == "Nantes — album photo"


def test_reconnect_required_uses_the_shared_orange_warning_icon(app):
    view = PhotoSourcesWidget(Translator("en"))
    card = _source_card(view, session_available=False)
    assert not card.connection_status_icon.isHidden()
    assert not card.connection_status_icon.pixmap().isNull()
    view.close()


def test_enabling_nominatim_selects_it_for_location_after_success(
    window, tmp_path, monkeypatch,
):
    from photoalbum.sources import PhotoMetadataPolicy

    service = window._project_service
    service.create(tmp_path / "nominatim-default.photoalbum")
    service.set_source_directory(tmp_path / "photos")
    window._load_project_settings()
    source_id = service.get_photo_source().id

    service.set_photo_metadata_policy(PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference="none",
        nominatim_enabled=False,
    ), source_id)
    monkeypatch.setattr(window._scan_controller, "refresh_metadata", lambda _source_id: None)
    window._source_policy_changed(source_id, PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference="none",
        nominatim_enabled=True,
    ))
    assert source_id in window._pending_nominatim_location_sources
    assert service.get_photo_metadata_policy(source_id).location_preference == "none"

    window._metadata_refresh_finished(source_id, True)

    policy = service.get_photo_metadata_policy(source_id)
    assert policy.nominatim_enabled
    assert policy.location_preference == "geocoding"
    assert source_id not in window._pending_nominatim_location_sources


def test_failed_first_nominatim_refresh_keeps_location_policy(
    window, tmp_path, monkeypatch,
):
    from photoalbum.sources import PhotoMetadataPolicy

    service = window._project_service
    service.create(tmp_path / "nominatim-failed.photoalbum")
    service.set_source_directory(tmp_path / "photos")
    window._load_project_settings()
    source_id = service.get_photo_source().id

    service.set_photo_metadata_policy(PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference="none",
        nominatim_enabled=False,
    ), source_id)
    monkeypatch.setattr(window._scan_controller, "refresh_metadata", lambda _source_id: None)
    window._source_policy_changed(source_id, PhotoMetadataPolicy(
        date_preference="exif",
        gps_preference="exif",
        location_preference="none",
        nominatim_enabled=True,
    ))
    window._metadata_refresh_finished(source_id, False)

    assert service.get_photo_metadata_policy(source_id).location_preference == "none"
    assert source_id not in window._pending_nominatim_location_sources
