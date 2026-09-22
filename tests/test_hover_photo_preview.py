from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from photoalbum.gui.hover_photo_preview import HoverPhotoPreview
from photoalbum.gui.preview_image_cache import PreviewImageCache


def preview_service():
    QApplication.instance() or QApplication([])
    cache = PreviewImageCache()
    cache._pool = SimpleNamespace(start=Mock())
    return HoverPhotoPreview(cache), cache


def finish(cache, token):
    image = QImage(550, 400, QImage.Format.Format_RGB32)
    image.fill(0xFF123456)
    cache._finished(token, image)


def test_hover_result_is_reused_and_keeps_common_resolution():
    preview, cache = preview_service()
    preview.schedule("photo.jpg", QPoint(10, 20))
    preview._request_image()
    assert cache._pool.start.call_count == 1
    token = next(iter(cache._active))
    assert token[3] == 550
    finish(cache, token)
    assert preview.preview is not None

    preview.cancel()
    preview.schedule("photo.jpg", QPoint(30, 40))
    preview._request_image()
    assert cache._pool.start.call_count == 1
    assert preview.preview is not None
    preview.cancel()


def test_cancel_during_hover_delay_never_starts_decode_or_shows_tooltip():
    app = QApplication.instance() or QApplication([])
    preview, cache = preview_service()
    preview.schedule("photo.jpg", QPoint())
    assert preview._timer.isActive()

    preview.cancel()
    # Deterministically exercise the timeout callback even though cancel()
    # stopped the actual timer before Qt could deliver it.
    preview._timer.timeout.emit()
    app.processEvents()

    assert not preview._timer.isActive()
    cache._pool.start.assert_not_called()
    assert preview.preview is None


def test_completed_decode_cannot_show_an_obsolete_hover():
    preview, cache = preview_service()
    preview.schedule("old.jpg", QPoint())
    preview._request_image()
    old_token = next(iter(cache._active))

    preview.schedule("new.jpg", QPoint())
    finish(cache, old_token)
    assert preview.preview is None

    preview._request_image()
    new_token = next(iter(cache._active))
    finish(cache, new_token)
    assert preview.preview is not None
    preview.cancel()


def test_clear_rejects_results_from_the_previous_project():
    preview, cache = preview_service()
    preview.schedule("photo.jpg", QPoint())
    preview._request_image()
    token = next(iter(cache._active))
    preview.clear()
    finish(cache, token)
    assert preview.preview is None
    assert not cache._cache
