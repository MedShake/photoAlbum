"""Native album pages retain keyboard access, scrolling and project settings."""
from dataclasses import replace

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QGroupBox, QScrollArea, QStyleFactory, QToolBox, QWidget

from photoalbum.app import ProjectService
from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.i18n import Translator
from photoalbum.template_engine import create_template_registry


@pytest.fixture(params=[name for name in QStyleFactory.keys()
                        if name.lower() in {"fusion", "windows", "windowsvista", "windows11"}])
def view(request, show_active_window):
    app = QApplication.instance() or QApplication([])
    old_style, old_palette = app.style().objectName(), app.palette()
    app.setStyle(request.param)
    widget = AlbumSettingsWidget(create_template_registry(), Translator("fr"))
    widget.resize(960, 450)
    show_active_window(widget)
    yield app, widget
    widget.close()
    widget.deleteLater()
    # Dispose of the widget before restoring the application's style/palette.
    QApplication.sendPostedEvents(widget, QEvent.Type.DeferredDelete)
    app.processEvents()
    app.setStyle(old_style)
    app.setPalette(old_palette)
    app.processEvents()


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_native_pages_follow_palette_and_keyboard_without_changing_settings(view, dark):
    app, widget = view
    palette = QPalette(app.palette())
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        palette.setColor(group, QPalette.Window, QColor("#202020" if dark else "#eeeeee"))
        palette.setColor(group, QPalette.WindowText, QColor("#eeeeee" if dark else "#202020"))
        palette.setColor(group, QPalette.Button, palette.color(group, QPalette.Window))
        palette.setColor(group, QPalette.ButtonText, palette.color(group, QPalette.WindowText))
    app.setPalette(palette)
    app.processEvents()
    toolbox = widget._settings_toolbox
    assert type(toolbox) is QToolBox
    assert all(type(child).__module__ == "PySide6.QtWidgets" for child in widget.findChildren(QWidget))
    assert all(child.styleSheet() == "" for child in widget.findChildren(QWidget))
    assert toolbox.palette().color(QPalette.Window) == app.palette().color(QPalette.Window)
    for index, title in widget._settings_sections.values():
        text = toolbox.itemText(index)
        assert text == title or text.startswith(f"{title} — ")
        assert toolbox.itemToolTip(index) == text
    snapshot = widget.settings()
    changes = QSignalSpy(widget.settings_changed)
    # Native shortcuts activate pages without numbering the visible titles.
    for index in (1, 4, 6, 0):
        changed = QSignalSpy(toolbox.currentChanged)
        QTest.keyClick(widget, Qt.Key.Key_1 + index, Qt.KeyboardModifier.AltModifier)
        assert changed.count() or changed.wait(1000)
        assert toolbox.currentIndex() == index
        assert toolbox.widget(index).isVisibleTo(widget)
        assert widget.settings() == snapshot
    assert changes.count() == 0
    assert not widget.grab().isNull()


@pytest.mark.parametrize("custom", [False, True], ids=["standard-format", "custom-format"])
def test_every_page_keeps_controls_compact_at_the_top_when_window_grows(view, custom):
    app, widget = view
    if custom:
        widget._page_format_combo.setCurrentIndex(widget._page_format_combo.findData("custom"))
    before = widget.settings()
    changes = QSignalSpy(widget.settings_changed)
    toolbox = widget._settings_toolbox
    for index in range(toolbox.count()):
        toolbox.setCurrentIndex(index)
        page = toolbox.widget(index)
        group = page if isinstance(page, QGroupBox) else page.findChild(QGroupBox)
        positions = []
        for height in (600, 1000, 600):
            widget.resize(960, height)
            for _ in range(3):
                app.processEvents()
            controls = [control for control in group.findChildren(QWidget)
                        if control.isVisibleTo(group)]
            assert controls
            # Spare height belongs below the form, never between its controls.
            assert group.y() == 0
            assert group.height() < page.height()
            positions.append((group.height(), [(control.geometry().y(), control.height())
                                               for control in controls]))
        assert positions[0] == positions[1] == positions[2]
        assert widget.settings() == before
    assert changes.count() == 0


def test_native_page_scrolls_large_forms_at_small_window_sizes(view):
    app, widget = view
    font = widget.font()
    font.setPointSize(font.pointSize() + 3)
    widget.setFont(font)
    widget.resize(800, 450)
    index = widget._settings_sections["dividers"][0]
    toolbox = widget._settings_toolbox
    toolbox.setCurrentIndex(index)
    for _ in range(3):
        app.processEvents()
    assert widget.height() == 450
    group = toolbox.widget(index)
    scroll = next(area for area in toolbox.findChildren(QScrollArea) if area.widget() is group)
    assert scroll.verticalScrollBar().maximum() > 0
    scroll.ensureWidgetVisible(widget._year_placement_combo)
    app.processEvents()
    bottom = widget._year_placement_combo.mapTo(
        scroll.viewport(), QPoint(0, widget._year_placement_combo.height()),
    ).y()
    assert bottom <= scroll.viewport().height()


@pytest.mark.parametrize("photo_choice", ["complex-auto-1-5", "complex-photo-5"])
def test_native_pages_preserve_settings_when_project_is_reopened(view, tmp_path, photo_choice):
    app, widget = view
    widget.set_available_years({2025, 2026})
    widget._page_format_combo.setCurrentIndex(widget._page_format_combo.findData("custom"))
    widget._custom_width_spin.setValue(185)
    widget._custom_height_spin.setValue(250)
    widget._custom_apply_button.click()
    widget._photo_page_combo.setCurrentIndex(widget._photo_page_combo.findData(photo_choice))
    widget._day_dividers_checkbox.setChecked(True)
    widget._month_dividers_checkbox.setChecked(False)
    widget._page_numbers_checkbox.setChecked(False)
    widget._page_multiple_4_checkbox.setChecked(True)
    widget._add_special_page(widget._front_matter_list, widget._front_matter_combo)
    widget._add_special_page(widget._back_matter_list, widget._back_matter_combo)
    settings = replace(widget.settings(), template_pack_settings={"msb": {"future": 42}})
    widget.set_settings(settings)
    titles = [widget._settings_toolbox.itemText(i) for i in range(7)]
    project = ProjectService()
    restored_view = None
    try:
        path = tmp_path / "native-pages.photoalbum"
        project.create(path)
        project.set_album_structure_settings(settings)
        project.close()
        project.open(path)
        restored_view = AlbumSettingsWidget(widget._registry, Translator("fr"))
        restored_view.set_available_years({2025, 2026})
        changes = QSignalSpy(restored_view.settings_changed)
        restored_view.set_settings(project.get_album_structure_settings())
        assert restored_view.settings() == settings
        assert [restored_view._settings_toolbox.itemText(i) for i in range(7)] == titles
        for index in range(7):
            restored_view._settings_toolbox.setCurrentIndex(index)
        assert restored_view.settings() == settings
        assert changes.count() == 0
    finally:
        project.close()
        if restored_view is not None:
            restored_view.close()
            restored_view.deleteLater()
            QApplication.sendPostedEvents(restored_view, QEvent.Type.DeferredDelete)
            app.processEvents()
