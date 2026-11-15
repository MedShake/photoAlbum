import sys
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLabel, QRadioButton, QTableWidget
from shiboken6 import delete, isValid

from photoalbum.gui.widgets.photo_places_widget import PhotoPlacesWidget
from photoalbum.models import Photo
from tests.qt_support import wait_events


@pytest.fixture
def qt_callback_errors(monkeypatch):
    errors = Mock()
    monkeypatch.setattr(sys, "excepthook", errors)
    yield errors
    errors.assert_not_called()


def queued_thumbnail(widget, path):
    photo = Photo(path=path, filename=path.name)
    label = widget._create_thumbnail_label(photo)
    label.setParent(widget)
    return label


def test_destroying_widget_cancels_thumbnail_timer(tmp_path, monkeypatch, qt_callback_errors):
    widget = PhotoPlacesWidget()
    load = Mock(wraps=widget._load_next_thumbnail)
    monkeypatch.setattr(widget, "_load_next_thumbnail", load)
    label = queued_thumbnail(widget, tmp_path / "photo.jpg")
    delete(widget)
    assert not isValid(label)
    wait_events(10)
    load.assert_not_called()


def test_destroyed_thumbnail_is_skipped_without_stopping_queue(tmp_path, monkeypatch, qt_callback_errors):
    widget = PhotoPlacesWidget()
    decode = Mock(return_value=None)
    monkeypatch.setattr(widget, "_thumbnail_pixmap", decode)
    dead = queued_thumbnail(widget, tmp_path / "dead.jpg")
    live_path = tmp_path / "live.jpg"
    live = queued_thumbnail(widget, live_path)
    delete(dead)
    wait_events(10)
    decode.assert_called_once_with(live_path)
    assert dead not in widget._thumbnail_labels
    assert live.text() == "—"
    assert not widget._thumbnail_queue
    assert not widget._thumbnail_loading


@pytest.mark.parametrize("available", [False, True])
def test_thumbnail_destroyed_during_decode_keeps_queue_running(
    tmp_path, monkeypatch, qt_callback_errors, available,
):
    widget = PhotoPlacesWidget()
    dead = queued_thumbnail(widget, tmp_path / "dead.jpg")
    live = queued_thumbnail(widget, tmp_path / "live.jpg")
    pixmap = QPixmap(40, 30) if available else None
    if pixmap is not None:
        pixmap.fill()

    def decode(path):
        if path.name == "dead.jpg":
            delete(dead)
        return pixmap

    decode = Mock(side_effect=decode)
    monkeypatch.setattr(widget, "_thumbnail_pixmap", decode)
    wait_events(10)
    assert decode.call_count == 2
    assert dead not in widget._thumbnail_labels
    assert not live.pixmap().isNull() if available else live.text() == "—"
    assert not widget._thumbnail_queue
    assert not widget._thumbnail_loading


@pytest.mark.parametrize("available", [False, True])
def test_widget_destroyed_during_thumbnail_decode(
    tmp_path, monkeypatch, qt_callback_errors, available,
):
    widget = PhotoPlacesWidget()
    queued_thumbnail(widget, tmp_path / "photo.jpg")
    pixmap = QPixmap(40, 30) if available else None
    if pixmap is not None:
        pixmap.fill()

    def decode(path):
        delete(widget)
        return pixmap

    decode = Mock(side_effect=decode)
    monkeypatch.setattr(widget, "_thumbnail_pixmap", decode)
    wait_events(10)
    decode.assert_called_once()
    assert not isValid(widget)


def test_thumbnail_queue_decodes_one_image_per_callback(tmp_path, monkeypatch):
    widget = PhotoPlacesWidget()
    callbacks = []
    monkeypatch.setattr(QTimer, "singleShot", lambda *args: callbacks.append(args[-1]))
    decode = Mock(return_value=None)
    monkeypatch.setattr(widget, "_thumbnail_pixmap", decode)
    first = queued_thumbnail(widget, tmp_path / "first.jpg")
    second = queued_thumbnail(widget, tmp_path / "second.jpg")
    decode.assert_not_called()
    assert len(callbacks) == 1
    callbacks.pop(0)()
    assert decode.call_count == 1
    assert first.text() == "—"
    assert second.text() == "…"
    callbacks.pop(0)()
    assert decode.call_count == 2
    assert second.text() == "—"
    callbacks.pop(0)()
    assert not widget._thumbnail_loading
    assert not callbacks


def test_reloading_same_identity_replaces_changed_thumbnail(tmp_path):
    app = QApplication.instance() or QApplication([])
    widget = PhotoPlacesWidget()
    path = tmp_path / "photo.png"
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    photo = Photo(path=path, filename=path.name, asset_id="same")
    image.fill(0xFFFF0000)
    assert image.save(str(path))
    widget.set_photos([photo])
    label = widget._create_thumbnail_label(photo)
    for _ in range(5):
        app.processEvents()
    assert label.pixmap().toImage().pixelColor(10, 10).name() == "#ff0000"
    image.fill(0xFF0000FF)
    assert image.save(str(path))
    widget.set_photos([photo])
    label = widget._create_thumbnail_label(photo)
    for _ in range(5):
        app.processEvents()
    assert label.pixmap().toImage().pixelColor(10, 10).name() == "#0000ff"
    widget.close()


@pytest.mark.parametrize("preload", [False, True])
def test_batch_dialog_loads_missing_thumbnails_and_reuses_cache(tmp_path, monkeypatch, preload):
    app = QApplication.instance() or QApplication([])
    widget = PhotoPlacesWidget()
    photos = []
    for name in ("a", "b", "outside"):
        path = tmp_path / f"{name}.jpg"
        image = QImage(40, 30, QImage.Format.Format_RGB32)
        image.fill(0xFF123456)
        assert image.save(str(path))
        photos.append(Photo(path=path, filename=path.name))
    widget._photos = photos
    decode = Mock(wraps=widget._thumbnail_pixmap)
    monkeypatch.setattr(widget, "_thumbnail_pixmap", decode)
    if preload:
        widget._create_thumbnail_label(photos[0])
        for _ in range(5):
            app.processEvents()
        assert decode.call_count == 1
    original_labels = set(widget._thumbnail_labels)
    monkeypatch.setattr(widget, "_group_location_candidates", lambda *args: photos[:2])
    checkbox = QCheckBox()
    checkbox.setProperty("location_key", "city")
    checkbox.setProperty("location_value", "Paris")

    def check_dialog(dialog):
        # Building the table never decodes images synchronously.
        assert decode.call_count == (1 if preload else 0)
        table = dialog.findChild(QTableWidget)
        assert table.rowCount() == 2
        for _ in range(10):
            app.processEvents()
        for row in range(2):
            labels = table.cellWidget(row, 1).findChildren(QLabel)
            assert any(not label.pixmap().isNull() for label in labels)
        assert decode.call_count == 2
        # Changing the action rebuilds candidates but reuses decoded images.
        dialog.findChildren(QRadioButton)[1].setChecked(True)
        for _ in range(5):
            app.processEvents()
        assert decode.call_count == 2
        assert len(widget._thumbnail_labels) == len(original_labels) + 2
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", check_dialog)
    widget._open_group_location_dialog(photos[0], checkbox)
    assert set(widget._thumbnail_labels) == original_labels
    assert not widget._thumbnail_queue
    assert str(photos[2].path) not in widget._thumbnail_cache
    widget.close()


def test_closing_batch_dialog_cancels_pending_thumbnails(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    widget = PhotoPlacesWidget()
    photo = Photo(path=tmp_path / "missing.jpg", filename="missing.jpg")
    monkeypatch.setattr(widget, "_group_location_candidates", lambda *args: [photo])
    decode = Mock(wraps=widget._thumbnail_pixmap)
    monkeypatch.setattr(widget, "_thumbnail_pixmap", decode)
    monkeypatch.setattr(QDialog, "exec", lambda dialog: QDialog.DialogCode.Rejected)
    checkbox = QCheckBox()
    checkbox.setProperty("location_key", "city")
    checkbox.setProperty("location_value", "Paris")
    widget._open_group_location_dialog(photo, checkbox)
    for _ in range(5):
        app.processEvents()
    decode.assert_not_called()
    assert not widget._thumbnail_queue
    assert not widget._thumbnail_labels
    widget.close()


def test_batch_dialog_thumbnails_use_the_shared_hover_preview(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    hover_preview = Mock()
    widget = PhotoPlacesWidget(hover_preview=hover_preview)
    path = tmp_path / "photo.jpg"
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(0xFF123456)
    assert image.save(str(path))
    photo = Photo(path=path, filename=path.name)
    widget._photos = [photo]
    monkeypatch.setattr(widget, "_group_location_candidates", lambda *args: [photo])
    checkbox = QCheckBox()
    checkbox.setProperty("location_key", "city")
    checkbox.setProperty("location_value", "Paris")

    def check_dialog(dialog):
        table = dialog.findChild(QTableWidget)
        thumbnail = table.cellWidget(0, 1).findChildren(QLabel)[0]
        app.sendEvent(thumbnail, QEvent(QEvent.Type.Enter))
        hover_preview.schedule.assert_called_once()
        assert hover_preview.schedule.call_args.args[0] == path
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", check_dialog)
    widget._open_group_location_dialog(photo, checkbox)
    hover_preview.cancel.assert_called()
    widget.close()
