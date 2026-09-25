from datetime import datetime
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDateTimeEdit, QDoubleSpinBox, QPushButton, QMessageBox

from photoalbum.app import ProjectService
from photoalbum.gui.main_window import MainWindow
from photoalbum.gui.photo_editor import PhotoEditor
from photoalbum.gui.scan_controller import ScanController
from photoalbum.gui.widgets.photo_sources_widget import PhotoSourcesWidget
from photoalbum.i18n import Translator
from photoalbum.models import Photo


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
    assert settings.photo_pages.template_id == 'photo-page-2'
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
    source, scan, recursive = Mock(), Mock(), Mock()
    view.source_requested.connect(source)
    view.scan_requested.connect(scan)
    view.recursive_changed.connect(recursive)
    view.browse_button.click()
    view.analyze_button.click()
    view.recursive_checkbox.setChecked(True)
    source.assert_called_once_with()
    scan.assert_called_once_with()
    recursive.assert_called_once_with(True)
    first = Photo(path=tmp_path / 'a.jpg', filename='a.jpg')
    second = Photo(path=tmp_path / 'z.jpg', filename='z.jpg')
    view.model.set_photos([first, second])
    view.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
    view.select_photo(first)
    selected = view.proxy_model.mapToSource(view.table.currentIndex())
    assert view.model.photo_at(selected.row()).path == first.path
    view.close()


def test_hover_preview_clears_on_model_reset_and_tab_hide(app, tmp_path):
    path = tmp_path / 'photo.jpg'
    Image.new('RGB', (100, 80), 'red').save(path)
    view = PhotoSourcesWidget(Translator('en'))
    view.model.set_photos([Photo(path=path, filename=path.name)])
    view.show()
    view._source_preview_row = 0
    view._show_pending_source_photo_preview()
    wait_until(app, lambda: view._hover_preview.preview is not None)
    view.model.clear()
    assert view._hover_preview.preview is None
    assert view._source_preview_row is None
    view.model.set_photos([Photo(path=path, filename=path.name)])
    view._source_preview_row = 0
    view._show_pending_source_photo_preview()
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
        service.set_manual_capture_datetime.assert_called_once_with(photo.path, replacement)
    elif action == 'restore':
        service.restore_original_capture_datetime.assert_called_once_with(photo.path)
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
            latitude, longitude = dialog.findChildren(QDoubleSpinBox)
            latitude.setValue(-12.3456789)
            longitude.setValue(78.1234567)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, 'exec', execute)
    editor.edit_gps(photo)
    if restore:
        service.restore_original_gps.assert_called_once_with(photo.path)
        editor._start_gps_geocoding.assert_called_once_with(photo.path, 30, 40)
    else:
        service.set_manual_gps.assert_called_once_with(photo.path, -12.3456789, 78.1234567)
        editor._start_gps_geocoding.assert_called_once_with(photo.path, -12.3456789, 78.1234567)


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


@pytest.mark.parametrize('failure', [False, True])
@pytest.mark.parametrize('orientation', ['portrait', 'landscape', 'custom'])
def test_pdf_worker_completes_or_fails_and_reenables_controls(window, app, tmp_path, monkeypatch, failure, orientation):
    from dataclasses import replace
    from photoalbum.album import PageOrientation
    from photoalbum.gui.widgets import pdf_export_widget as module
    from photoalbum.export import PdfExportContent

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
    window._album_build_result = SimpleNamespace(pagination=SimpleNamespace(pages=[object()]), total_page_count=5)
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
    if failure:
        assert 'test export failure' in widget._pdf_log_view.toPlainText()
    else:
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
    assert not view.analyze_button.isEnabled()
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
