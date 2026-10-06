"""Actual tree-row geometry must follow content, in both resize directions."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import sys

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QCheckBox, QWidget

from photoalbum.gui.widgets.photo_places_widget import PhotoPlacesWidget
from photoalbum.models import LocationComponent, Photo


@pytest.fixture
def view():
    app = QApplication.instance() or QApplication([])
    save = Mock()

    # Keep geometry tests independent from the window manager.
    # A top-level QWidget may have resize requests constrained by
    # the desktop; as a child, its requested geometry is deterministic.
    host = QWidget()
    host.resize(2200, 900)

    widget = PhotoPlacesWidget(
        parent=host,
        save_location_override=save,
    )
    components = tuple(LocationComponent(key=k, value=v) for k, v in [
        ('road', 'Boulevard des longues promenades'),
        ('city', 'Saint-Martin-de-la-Montagne'),
        ('county', 'Département de démonstration'),
        ('state', 'Région des grandes plaines'), ('country', 'France'),
    ])
    widget._caption_result = lambda p: SimpleNamespace(
        candidates=components if p.filename != 'no-gps' else (),
        selected=components[-1:] if p.filename != 'no-gps' else (), caption='France',
    )
    photos = [Photo(path=Path('/tmp') / name, filename=name,
                    capture_datetime=datetime(2025, month, 1))
              for name, month in [('gps', 3), ('no-gps', 3), ('later', 4)]]
    widget.resize(1400, 700)
    host.show()
    widget.show()
    widget.set_photos(photos)
    widget._tree.topLevelItem(0).setExpanded(True)
    widget._tree.topLevelItem(0).child(0).setExpanded(True)
    def settle():
        # Drain normal Qt layout/model events, without production timers or sleeps.
        for _ in range(10):
            app.processEvents()
    settle()
    yield widget, photos, save, settle
    host.close()


def assert_fits(widget, photo):
    item, editor, flow = widget._editor_rows[photo.identity]
    rect = widget._tree.visualItemRect(item)
    assert rect.height() == item.sizeHint(3).height()
    assert item.sizeHint(3).isValid()
    for column in range(4):
        cell = widget._tree.itemWidget(item, column)
        assert cell.height() >= cell.sizeHint().height()
    if flow.parentWidget().isVisible():
        assert flow.parentWidget().height() >= flow.heightForWidth(flow.parentWidget().width())
        for check in flow.parentWidget().findChildren(QCheckBox):
            assert check.geometry().bottom() < flow.parentWidget().height()
    caption = widget._caption_editors[photo.identity]
    assert caption.mapTo(editor, QPoint(0, caption.height())).y() <= editor.height()
    return rect.height()


def test_resize_both_directions_and_mode_switches(view):
    widget, photos, save, settle = view
    photo = photos[0]
    combo = widget._location_mode_boxes[photo.identity]
    editor = widget._editor_rows[photo.identity][1]
    caption = widget._caption_editors[photo.identity]
    wide = assert_fits(widget, photo)
    widget.resize(950, 700)
    settle()
    narrow = assert_fits(widget, photo)
    assert narrow > wide
    combo.setCurrentIndex(1)
    settle()
    custom = assert_fits(widget, photo)
    assert custom < narrow
    assert save.call_count == 1
    combo.setCurrentIndex(0)
    settle()
    assert assert_fits(widget, photo) == narrow
    assert save.call_count == 2
    widget.resize(1400, 700)
    settle()
    assert assert_fits(widget, photo) == wide
    for width in (1000, 1700, 950, 1400):
        widget.resize(width, 700)
        settle()
        assert_fits(widget, photo)
    assert widget._editor_rows[photo.identity][1] is editor
    assert widget._caption_editors[photo.identity] is caption
    assert widget._materialized_months == {(2025, 3)}
    assert photos[2].identity not in widget._editor_rows


def test_truth_text_and_column_width_change_row_height(view):
    widget, photos, _, settle = view
    photo = photos[1]
    initial = assert_fits(widget, photo)
    photo.caption = 'A long caption with several words. ' * 15
    widget._after_editorial_change(photo)
    settle()
    long = assert_fits(widget, photo)
    assert long > initial
    widget._tree.setColumnWidth(2, 500)
    settle()
    assert assert_fits(widget, photo) < long
    photo.caption = 'Short'
    widget._after_editorial_change(photo)
    settle()
    assert assert_fits(widget, photo) == initial


def test_hidden_view_and_lazy_month_expansion(view):
    widget, photos, _, settle = view
    widget.hide()
    widget.resize(950, 700)
    settle()
    widget.show()
    settle()
    narrow = assert_fits(widget, photos[0])
    widget.resize(1700, 700)
    settle()
    assert assert_fits(widget, photos[0]) < narrow
    year = widget._tree.topLevelItem(0)
    april = year.child(1)
    april.setExpanded(True)
    settle()
    assert widget._materialized_months == {(2025, 3), (2025, 4)}
    assert_fits(widget, photos[2])


def test_custom_location_and_caption_keep_horizontal_alignment(view):
    widget, photos, _, settle = view
    combo = widget._location_mode_boxes[photos[0].identity]
    combo.setCurrentIndex(1)
    settle()
    starts = []
    for photo in photos[:2]:
        root = widget._editor_rows[photo.identity][1]
        location = widget._location_mode_widgets[photo.identity][2]
        caption = widget._caption_editors[photo.identity]
        x = location.mapTo(root, QPoint()).x()
        assert x == caption.mapTo(root, QPoint()).x()
        assert location.width() == caption.width()
        starts.append(x)
    assert starts[0] == starts[1]


def test_rebuilding_materialized_rows_ignores_stale_qt_geometry_events(
    view, monkeypatch,
):
    widget, photos, _, settle = view
    errors = []
    monkeypatch.setattr(
        sys,
        "excepthook",
        lambda exception_type, value, traceback: errors.append(value),
    )
    stale_generation = widget._tree_generation

    # Source activation/policy changes rebuild this view several times in one
    # event-loop turn. Old _PhotoCell LayoutRequest events may arrive later.
    for index in range(8):
        widget.set_source_labels({"local": f"Provider {index}"})
        widget.set_photos(photos)
        year = widget._tree.topLevelItem(0)
        year.setExpanded(True)
        year.child(0).setExpanded(True)

    widget._update_photo_item_height(photos[0].identity, stale_generation)
    settle()

    assert errors == []
    assert_fits(widget, photos[0])
