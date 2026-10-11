"""Regression checks for the V8 compact interface, paths and export safety."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt, QSettings, QStandardPaths
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

from photoalbum.album import PlanItemKind
from photoalbum.gui import default_paths
from photoalbum.gui.main_window import MainWindow
from photoalbum.gui.widgets.accordion_section import AccordionSection
from photoalbum.gui.widgets.album_preview_widget import AlbumPreviewWidget
from photoalbum.i18n import Translator


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def private_paths_settings(tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "paths.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(default_paths, "_settings", lambda: settings)
    return settings


def test_accordion_hover_surface_covers_full_row_with_native_selection(app):
    section = AccordionSection("Format", QWidget())
    try:
        section.resize(600, 120)
        section.set_summary("A4 — 210 × 297 mm")
        section.show()
        app.processEvents()
        # A full-width native QToolButton keeps the previous checked/pressed
        # behaviour; no custom stylesheet should draw a white/blue focus box.
        assert section._heading.styleSheet() == ""
        assert section._heading.autoRaise()
        assert section._heading.isCheckable()
        assert section._heading.focusPolicy() == Qt.FocusPolicy.StrongFocus
        assert section.layout().itemAt(0).widget() is section._heading
        assert section._heading.width() == section.width()
        assert section._summary.parentWidget() is section._heading
        assert section._summary.width() >= section._summary.sizeHint().width()
        assert section._summary.testAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        # Clicking even near the far-right summary toggles the section.
        near_summary = QPoint(section._heading.width() - 10,
                              section._heading.height() // 2)
        QTest.mouseClick(section._heading, Qt.MouseButton.LeftButton, pos=near_summary)
        assert section.expanded
        QTest.mouseClick(section._heading, Qt.MouseButton.LeftButton, pos=near_summary)
        assert not section.expanded
    finally:
        section.close()


@pytest.mark.parametrize("kind", [PlanItemKind.SPECIAL_PAGE, PlanItemKind.BODY_SPECIAL_PAGE])
def test_special_page_has_ordinary_number_in_preview_ruler(kind):
    special = SimpleNamespace(
        kind=kind, number=25, photos=(), year=None, month=None, day=None,
    )
    navigation = AlbumPreviewWidget._navigation_page(special, Translator("fr"))
    assert navigation.short_label == '25'
    assert navigation.page_number == 25
    assert 'sp.' not in navigation.page_label.lower()
    assert 'spéciale' not in navigation.page_label.lower()


def test_documents_or_home_resolves_platform_locations(tmp_path, monkeypatch):
    documents = tmp_path / 'Documents'
    documents.mkdir()
    monkeypatch.setattr(QStandardPaths, 'writableLocation', lambda _: str(documents))
    assert default_paths.documents_or_home() == documents
    documents.rmdir()
    assert default_paths.documents_or_home() == Path.home()


def test_project_directory_remembers_last_location(tmp_path, monkeypatch, private_paths_settings):
    monkeypatch.setattr(default_paths, "documents_or_home", lambda: tmp_path)
    assert default_paths.project_directory() == tmp_path
    directory = tmp_path / 'Albums'
    directory.mkdir()
    default_paths.remember_project_directory(directory / 'Family.photoalbum')
    assert default_paths.project_directory() == directory
    directory.rmdir()
    assert default_paths.project_directory() == tmp_path


def test_pdf_default_is_next_to_project_and_remembers_its_own_export_dir(
    tmp_path, private_paths_settings,
):
    project = tmp_path / 'Summer.photoalbum'
    another = tmp_path / 'Winter.photoalbum'
    assert default_paths.pdf_destination(project) == tmp_path / 'Summer.pdf'
    elsewhere = tmp_path / 'Exports'
    elsewhere.mkdir()
    default_paths.remember_pdf_directory(project, elsewhere / 'Custom.pdf')
    assert default_paths.pdf_destination(project) == elsewhere / 'Summer.pdf'
    assert default_paths.pdf_destination(another) == tmp_path / 'Winter.pdf'
    elsewhere.rmdir()
    assert default_paths.pdf_destination(project) == tmp_path / 'Summer.pdf'


def test_new_project_dialog_starts_from_documents_or_previous_directory(
    app, tmp_path, monkeypatch, private_paths_settings,
):
    monkeypatch.setattr(default_paths, 'documents_or_home', lambda: tmp_path)
    observed = []
    monkeypatch.setattr(
        QFileDialog, 'getSaveFileName',
        lambda parent, caption, directory, file_filter: (
            observed.append(directory) or '', ''
        ),
    )
    window = MainWindow()
    try:
        window._new_project()
        assert observed[-1] == str(tmp_path)
        previous = tmp_path / 'Albums'
        previous.mkdir()
        default_paths.remember_project_directory(previous / 'A.photoalbum')
        window._new_project()
        assert observed[-1] == str(previous)
    finally:
        window.close()


def test_pdf_destination_is_seeded_on_project_load_and_changes_on_switch(
    app, tmp_path, private_paths_settings,
):
    window = MainWindow()
    try:
        one = tmp_path / 'First.photoalbum'
        other = tmp_path / 'Second.photoalbum'
        window._project_service.create(one)
        window._load_project_settings()
        assert window._pdf_widget._pdf_output_edit.text() == str(tmp_path / 'First.pdf')
        window._pdf_widget._pdf_output_edit.setText(str(tmp_path / 'Manual.pdf'))
        window._pdf_widget.set_project_settings(window._pdf_widget.project_settings())
        assert window._pdf_widget._pdf_output_edit.text() == str(tmp_path / 'Manual.pdf')
        window._project_service.close()
        window._project_service.create(other)
        window._load_project_settings()
        assert window._pdf_widget._pdf_output_edit.text() == str(tmp_path / 'Second.pdf')
    finally:
        window.close()


def test_pdf_export_locks_other_tabs_and_project_actions_and_restores_them(
    app, tmp_path, monkeypatch,
):
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Cancel)
    window = MainWindow()
    try:
        window._project_service.create(tmp_path / 'A.photoalbum')
        window._update_project_state()
        # No photos: the PDF tab must still stay accessible *during* export.
        window._tabs.setTabEnabled(5, True)
        window._pdf_widget.running_changed.emit(True)
        assert window._tabs.currentWidget() is window._pdf_widget
        assert window._tabs.isTabEnabled(5)
        assert all(not window._tabs.isTabEnabled(i) for i in range(5))
        assert not window._new_project_action.isEnabled()
        assert not window._open_project_action.isEnabled()
        assert not window._close_project_action.isEnabled()
        assert not window._project_rename_button.isEnabled()
        assert not window._cache_action.isEnabled()

        # Even direct slot invocations cannot change project while locked.
        window._pdf_widget._pdf_thread = object()
        original_path = window._project_service.project_path
        window._close_project()
        assert window._project_service.project_path == original_path
        window._pdf_widget._pdf_thread = None

        window._pdf_widget.running_changed.emit(False)
        assert window._tabs.isTabEnabled(0)
        assert window._new_project_action.isEnabled()
        assert window._open_project_action.isEnabled()
        assert window._close_project_action.isEnabled()
        assert window._project_rename_button.isEnabled()
        assert window._cache_action.isEnabled()
    finally:
        window._pdf_widget._pdf_thread = None
        window.close()


def test_pdf_export_start_failure_restores_controls(app, tmp_path, monkeypatch):
    from photoalbum.gui.widgets import pdf_export_widget as module

    class BrokenService:
        def __init__(self, translator):
            raise RuntimeError('Engine unavailable')

    monkeypatch.setattr(module, 'PdfExportService', BrokenService)
    # An expected failure must not open a modal error dialog during pytest.
    # Capture the user-facing message instead so that the test stays unattended.
    shown_errors = []

    def capture_error_dialog(parent, title, message):
        shown_errors.append(message)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, 'critical', capture_error_dialog)
    window = MainWindow()
    errors = []
    window._pdf_widget.error.connect(errors.append)
    try:
        window._project_service.create(tmp_path / 'A.photoalbum')
        window._load_project_settings()
        widget = window._pdf_widget
        window._album_build_result = SimpleNamespace(
            pagination=SimpleNamespace(pages=[object()]),
            template_photos=(), total_page_count=5,
        )
        widget._pdf_content_covers_radio.setChecked(True)
        widget.generate()
        assert not widget.is_running
        assert widget.generate_button.isEnabled()
        assert widget._pdf_output_button.isEnabled()
        assert widget._options_container.isEnabled()
        assert not widget._pdf_output_edit.isReadOnly()
        assert not window._pdf_export_running
        assert window._new_project_action.isEnabled()
        # Export errors shown to the user remain localized and do not expose
        # raw exceptions. The controls must nevertheless be restored.
        assert errors == [window._translator.tr("render.generate_error")]
        assert shown_errors == errors
        assert "Engine unavailable" not in errors[0]
    finally:
        window.close()


def test_prebuilt_album_keeps_pdf_tab_enabled_even_without_regular_photos(app, tmp_path):
    """An exportable album must not become disabled after a PDF worker finishes."""
    window = MainWindow()
    try:
        window._project_service.create(tmp_path / "CoverOnly.photoalbum")
        window._album_build_result = SimpleNamespace(
            pagination=SimpleNamespace(pages=[object()]),
        )
        window._set_scan_running(False)
        assert window._tabs.isTabEnabled(5)
        assert window._pdf_widget._options_container.isEnabled()

        window._pdf_widget.running_changed.emit(True)
        assert window._tabs.currentWidget() is window._pdf_widget
        assert all(not window._tabs.isTabEnabled(i) for i in range(5))
        # MainWindow's signal only controls tab availability; the PDF widget
        # disables its own options when generation actually starts.
        window._pdf_widget.running_changed.emit(False)

        assert window._tabs.isTabEnabled(5)
        assert window._pdf_widget._options_container.isEnabled()

        window._album_build_result = None
        window._set_scan_running(False)
        assert not window._tabs.isTabEnabled(5)
    finally:
        window.close()


def test_cache_action_stays_accessible_during_scan_but_not_pdf_export(app):
    window = MainWindow()
    try:
        window._set_scan_running(True)
        assert window._cache_action.isEnabled()
        window._pdf_widget.running_changed.emit(True)
        assert not window._cache_action.isEnabled()
        window._pdf_widget.running_changed.emit(False)
        assert window._cache_action.isEnabled()
    finally:
        window.close()
