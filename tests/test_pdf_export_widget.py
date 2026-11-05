"""Native PDF options retain compact geometry, summaries and preferences."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QGroupBox, QScrollArea, QStyleFactory, QToolBox, QWidget

from photoalbum.album import AlbumStructureSettings, DividerSettings, PhotoPageSettings
from photoalbum.app import ProjectService
from photoalbum.gui.widgets.pdf_export_widget import PdfExportWidget
from photoalbum.i18n import Translator
from photoalbum.project_metadata import PdfExportSettings, ProjectPdfMetadata


@pytest.fixture(params=[name for name in QStyleFactory.keys()
                        if name.lower() in {"fusion", "windows", "windowsvista", "windows11"}])
def app(request):
    app = QApplication.instance() or QApplication([])
    old_style, old_palette = app.style().objectName(), app.palette()
    app.setStyle(request.param)
    yield app
    app.setStyle(old_style)
    app.setPalette(old_palette)
    app.processEvents()


def make_widget(language="fr", project=None):
    return PdfExportWidget(
        translator=Translator(language),
        project_service=project if project is not None else SimpleNamespace(is_open=False),
        settings_provider=lambda: AlbumStructureSettings(
            covers={}, month_dividers=DividerSettings(False, "month-divider-simple"),
            year_dividers=DividerSettings(False, "year-divider-classic"),
            day_dividers=DividerSettings(False, "day-divider-simple"),
            photo_pages=PhotoPageSettings("photo-page-1"),
        ),
        result_provider=lambda: None,
        before_export=lambda: None,
    )


@pytest.fixture
def view(app):
    widget = make_widget()
    widget.resize(960, 450)
    widget.show()
    app.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


def summary(widget, key):
    index, title = widget._option_sections[key]
    text = widget._options_container.itemText(index)
    assert text == title or text.startswith(f"{title} — ")
    assert widget._options_container.itemToolTip(index) == text
    return text.removeprefix(f"{title} — ") if text != title else ""


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_native_options_follow_palette_and_keyboard_without_losing_output(view, app, dark):
    palette = QPalette(app.palette())
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        palette.setColor(group, QPalette.Window, QColor("#202020" if dark else "#eeeeee"))
        palette.setColor(group, QPalette.WindowText, QColor("#eeeeee" if dark else "#202020"))
        palette.setColor(group, QPalette.Base, QColor("#181818" if dark else "#ffffff"))
        palette.setColor(group, QPalette.Text, palette.color(group, QPalette.WindowText))
        palette.setColor(group, QPalette.Button, palette.color(group, QPalette.Window))
        palette.setColor(group, QPalette.ButtonText, palette.color(group, QPalette.WindowText))
    app.setPalette(palette)
    app.processEvents()
    toolbox = view._options_container
    assert type(toolbox) is QToolBox
    assert all(type(child).__module__ == "PySide6.QtWidgets" for child in view.findChildren(QWidget))
    assert all(child.styleSheet() == "" for child in view.findChildren(QWidget))
    assert toolbox.palette().color(QPalette.Window) == app.palette().color(QPalette.Window)
    view._pdf_output_edit.setText("chosen-output.pdf")
    before = view.project_settings()
    for index in (1, 2, 0):
        changed = QSignalSpy(toolbox.currentChanged)
        QTest.keyClick(view, Qt.Key.Key_1 + index, Qt.KeyboardModifier.AltModifier)
        assert changed.count() or changed.wait(1000)
        assert toolbox.currentIndex() == index
        assert toolbox.widget(index).isVisibleTo(view)
        assert view.project_settings() == before
        assert view._pdf_output_edit.text() == "chosen-output.pdf"
        assert view._pdf_output_edit.isVisibleTo(view)
        assert view.generate_button.isVisibleTo(view)
        assert not toolbox.isAncestorOf(view._pdf_output_edit)
        assert not toolbox.isAncestorOf(view.generate_button)
    assert not view.grab().isNull()


def test_all_pdf_pages_keep_controls_at_the_top_when_window_grows(view, app):
    toolbox = view._options_container
    before = view.project_settings()
    for index in range(toolbox.count()):
        toolbox.setCurrentIndex(index)
        page = toolbox.widget(index)
        group = page.findChild(QGroupBox)
        positions = []
        for height in (450, 900, 450):
            view.resize(960, height)
            for _ in range(3):
                app.processEvents()
            assert group.y() == 0
            assert group.height() < page.height()
            controls = [control for control in group.findChildren(QWidget) if control.isVisibleTo(group)]
            positions.append((group.height(), [(control.y(), control.height()) for control in controls]))
        assert positions[0] == positions[1] == positions[2]
        assert view.project_settings() == before


def test_pdf_metadata_can_scroll_on_small_windows_with_larger_fonts(view, app):
    font = view.font()
    font.setPointSize(font.pointSize() + 3)
    view.setFont(font)
    toolbox = view._options_container
    toolbox.setCurrentIndex(view._option_sections["metadata"][0])
    for _ in range(3):
        app.processEvents()
    height = max(260, view.minimumSizeHint().height() + 16)
    view.resize(800, height)
    for _ in range(3):
        app.processEvents()
    assert view.height() == height
    page = toolbox.currentWidget()
    scroll = next(area for area in toolbox.findChildren(QScrollArea) if area.widget() is page)
    assert scroll.verticalScrollBar().maximum() > 0
    scroll.ensureWidgetVisible(view._pdf_keywords_edit)
    app.processEvents()
    bottom = view._pdf_keywords_edit.mapTo(scroll.viewport(), QPoint(0, view._pdf_keywords_edit.height())).y()
    assert bottom <= scroll.viewport().height()
    assert view._pdf_output_edit.isVisibleTo(view)
    assert view.generate_button.isVisibleTo(view)


@pytest.mark.parametrize("language", ["fr", "en"])
def test_pdf_summaries_follow_content_resolution_and_committed_metadata(app, language):
    widget = make_widget(language)
    try:
        for radio in (widget._pdf_content_covers_radio, widget._pdf_content_body_radio,
                      widget._pdf_content_complete_radio):
            radio.setChecked(True)
            assert summary(widget, "content") == radio.text()
        widget._pdf_dpi_combo.setCurrentIndex(widget._pdf_dpi_combo.findData(600))
        assert summary(widget, "quality") == widget._pdf_dpi_combo.currentText()
        assert "600" in widget._pdf_pixel_size_label.text()
        widget._pdf_title_edit.setText("  Voyage en famille  ")
        widget._pdf_title_edit.editingFinished.emit()
        assert summary(widget, "metadata") == "Voyage en famille"
        widget._pdf_title_edit.clear()
        widget._pdf_title_edit.editingFinished.emit()
        assert summary(widget, "metadata") == ""
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


@pytest.mark.parametrize("content", ["complete", "covers", "body"])
def test_pdf_preferences_survive_project_reopening_and_page_navigation(app, tmp_path, content):
    project = ProjectService()
    widget = restored = None
    try:
        path = tmp_path / "pdf-options.photoalbum"
        project.create(path)
        widget = make_widget(project=project)
        save = Mock(wraps=project.set_pdf_export_settings)
        project.set_pdf_export_settings = save
        widget.set_project_settings(PdfExportSettings())
        assert save.call_count == 0
        widget._pdf_output_edit.setText("custom-output.pdf")
        for editor, text in ((widget._pdf_title_edit, "Mon PDF"), (widget._pdf_author_edit, "Auteur"),
                             (widget._pdf_subject_edit, "Vacances"), (widget._pdf_keywords_edit, "mer, famille")):
            editor.setText(text)
            editor.editingFinished.emit()
        widget._pdf_dpi_combo.setCurrentIndex(widget._pdf_dpi_combo.findData(150))
        {"complete": widget._pdf_content_complete_radio, "covers": widget._pdf_content_covers_radio,
         "body": widget._pdf_content_body_radio}[content].setChecked(True)
        expected = PdfExportSettings(ProjectPdfMetadata("Mon PDF", "Auteur", "Vacances", "mer, famille"), 150, content)
        assert project.get_pdf_export_settings() == expected
        titles = [widget._options_container.itemText(i) for i in range(3)]
        save.reset_mock()
        for index in range(3):
            widget._options_container.setCurrentIndex(index)
        widget.set_project_settings(expected)
        assert save.call_count == 0
        assert widget._pdf_output_edit.text() == "custom-output.pdf"
        project.close()
        project.open(path)
        restored = make_widget(project=project)
        restored.set_project_settings(project.get_pdf_export_settings())
        assert restored.project_settings() == expected
        assert [restored._options_container.itemText(i) for i in range(3)] == titles
    finally:
        project.close()
        for window in (widget, restored):
            if window is not None:
                window.close()
                window.deleteLater()
        app.processEvents()
