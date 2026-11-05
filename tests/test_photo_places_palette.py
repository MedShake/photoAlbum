"""Native editorial controls must remain readable when Qt's palette changes."""
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel

from photoalbum.gui.widgets.photo_places_widget import PhotoPlacesWidget
from photoalbum.models import LocationSource, Photo


GROUPS = (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled)


def editorial_palette(dark):
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#202020" if dark else "#eeeeee",
        QPalette.ColorRole.WindowText: "#eeeeee" if dark else "#202020",
        QPalette.ColorRole.Base: "#181818" if dark else "#ffffff",
        QPalette.ColorRole.AlternateBase: "#303030" if dark else "#dddddd",
        QPalette.ColorRole.Button: "#383838" if dark else "#e8e8e8",
        QPalette.ColorRole.ButtonText: "#ededed" if dark else "#121212",
        QPalette.ColorRole.Highlight: "#385f90",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: "#999999" if dark else "#666666",
    }
    for group in GROUPS:
        for role, value in colors.items():
            palette.setColor(group, role, QColor(value))
        text = ("#a0a0a0" if dark else "#606060") if group == QPalette.ColorGroup.Disabled else (
            "#f0f0f0" if dark else "#101010"
        )
        if group == QPalette.ColorGroup.Inactive:
            text = "#dedede" if dark else "#303030"
        palette.setColor(group, QPalette.ColorRole.Text, QColor(text))
    return palette


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=[False, True], ids=["light", "dark"])
def view(app, request):
    original_palette = app.palette()
    app.setPalette(editorial_palette(request.param))
    widget = PhotoPlacesWidget()
    widget.resize(1500, 800)
    photos = [
        Photo(path=Path(f"/missing/palette-{i}.jpg"), filename=f"palette-{i}.jpg",
              capture_datetime=date, caption=f"Caption {i}",
              location_source=LocationSource.GEOCODING,
              raw_location_data={"address": {"city": "Paris", "country": "France"}})
        for i, date in enumerate([
            datetime(2026, 1, 1), datetime(2026, 1, 2), datetime(2026, 2, 1), None, None,
        ])
    ]
    widget.set_photos(photos)
    widget.show()
    year = widget._tree.topLevelItem(0)
    year.setExpanded(True)
    for index in range(year.childCount()):
        year.child(index).setExpanded(True)
    app.processEvents()
    yield widget, photos, request.param
    widget.close()
    widget.deleteLater()
    app.processEvents()
    app.setPalette(original_palette)
    app.processEvents()


def assert_row_colors(view, photos):
    palette = view._tree.palette()
    for photo, role in zip(photos[:3], [QPalette.AlternateBase, QPalette.Base, QPalette.AlternateBase]):
        item = view._photo_items[photo.identity]
        for column in range(view._tree.columnCount()):
            assert item.background(column) == palette.brush(role)
            cell = view._tree.itemWidget(item, column)
            for group in GROUPS:
                assert cell.palette().brush(group, QPalette.Window) == palette.brush(group, role)
                assert cell.palette().brush(group, QPalette.WindowText) == palette.brush(group, QPalette.Text)
            for label in cell.findChildren(QLabel):
                assert label.palette().brush(QPalette.WindowText) == palette.brush(QPalette.Text)
    for index, role in [(1, QPalette.Base), (2, QPalette.AlternateBase)]:
        row = view._undated_layout.itemAt(index).widget()
        for group in GROUPS:
            assert row.palette().brush(group, QPalette.Window) == palette.brush(group, role)
            assert row.palette().brush(group, QPalette.WindowText) == palette.brush(group, QPalette.Text)


def assert_text_is_painted(control, role):
    expected = control.palette().color(role)
    image = control.grab().toImage()
    # Small native fonts use subpixel antialiasing; their strokes need not
    # contain a pixel exactly equal to the requested text color.
    assert any(max(abs(actual - target) for actual, target in zip(
        image.pixelColor(x, y).getRgb()[:3], expected.getRgb()[:3],
    )) <= 16 for y in range(image.height()) for x in range(image.width()))


def test_alternating_rows_and_embedded_text_follow_palette(view):
    widget, photos, dark = view
    assert widget._tree.palette().color(QPalette.Text) == editorial_palette(dark).color(QPalette.Text)
    assert_row_colors(widget, photos)
    for photo in photos[:3]:
        combo = widget._location_mode_boxes[photo.identity]
        assert combo.findData("geocoding") >= 0  # The Nominatim selector is present.
        caption = widget._caption_editors[photo.identity]
        location = widget._location_mode_widgets[photo.identity][2]
        for control in (combo, caption, location):
            assert control.styleSheet() == ""
            for group in GROUPS:
                for role in (QPalette.Base, QPalette.Text, QPalette.Button, QPalette.ButtonText,
                             QPalette.Highlight, QPalette.HighlightedText, QPalette.PlaceholderText):
                    assert control.palette().brush(group, role) == widget._tree.palette().brush(group, role)
        assert_text_is_painted(combo, combo.foregroundRole())
        assert_text_is_painted(caption, QPalette.Text)


def test_palette_switch_preserves_editors_focus_and_text_selection(view, app):
    widget, photos, dark = view
    caption = widget._caption_editors[photos[0].identity]
    caption.setFocus(Qt.FocusReason.TabFocusReason)
    caption.selectAll()
    app.processEvents()
    assert caption.hasFocus()
    app.setPalette(editorial_palette(not dark))
    app.processEvents()
    assert widget._tree.palette().color(QPalette.Text) == editorial_palette(not dark).color(QPalette.Text)
    assert_row_colors(widget, photos)
    assert widget._caption_editors[photos[0].identity] is caption
    assert caption.hasFocus()
    assert caption.selectedText() == photos[0].caption


def test_checkboxes_keep_native_keyboard_and_disabled_states(view, app):
    widget, photos, _ = view
    automatic = widget._location_mode_widgets[photos[0].identity][0]
    checkbox = automatic.findChild(QCheckBox)
    assert type(checkbox) is QCheckBox
    assert checkbox.styleSheet() == ""
    assert_text_is_painted(checkbox, QPalette.WindowText)
    for group in GROUPS:
        assert checkbox.palette().brush(group, QPalette.WindowText) == widget._tree.palette().brush(group, QPalette.Text)
    checkbox.setFocus(Qt.FocusReason.TabFocusReason)
    before = checkbox.isChecked()
    QTest.keyClick(checkbox, Qt.Key.Key_Space)
    assert checkbox.isChecked() != before
    widget.setEnabled(False)
    app.processEvents()
    assert not checkbox.isEnabled()
    assert checkbox.palette().currentColorGroup() == QPalette.ColorGroup.Disabled
    assert_text_is_painted(checkbox, QPalette.WindowText)
    assert_row_colors(widget, photos)
    widget.setEnabled(True)
    app.processEvents()
    assert checkbox.isEnabled()
    assert checkbox.isChecked() != before
