"""Shared asynchronous loading and display of photo hover previews."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QSize, QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel

from photoalbum.gui.preview_image_cache import PreviewImageCache


HOVER_PREVIEW_SIZE = QSize(550, 550)
HOVER_PREVIEW_DELAY_MS = 350


class HoverPhotoPreview(QObject):
    """Coordinate one application-wide hover tooltip and its image cache."""

    def __init__(
        self,
        cache: PreviewImageCache,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cache = cache
        self._cache.set_resolution(
            HOVER_PREVIEW_SIZE.width(),
            HOVER_PREVIEW_SIZE.height(),
            1,
        )
        self._cache.ready.connect(self._image_ready)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(HOVER_PREVIEW_DELAY_MS)
        self._timer.timeout.connect(self._request_image)

        self._path: str | None = None
        self._position = QPoint()
        self._preview: QLabel | None = None

    @property
    def preview(self) -> QLabel | None:
        return self._preview

    def schedule(self, path: str | Path, position: QPoint) -> None:
        self.cancel()
        self._path = str(path)
        self._position = QPoint(position)
        self._timer.start()

    def update_position(self, position: QPoint) -> None:
        self._position = QPoint(position)

    def cancel(self) -> None:
        self._timer.stop()
        self._path = None
        self._hide()

    def clear(self) -> None:
        """Discard all state when the active project is replaced or closed."""
        self.cancel()
        self._cache.clear()

    def invalidate_changed_sources(self) -> None:
        self._cache.invalidate_changed_sources()

    def _request_image(self) -> None:
        # Normally the single-shot timer is already inactive here. Stopping it
        # also makes explicit/immediate requests obey the same ready-state rule.
        self._timer.stop()
        path = self._path
        if path is None:
            return

        self._cache.invalidate_changed_sources()
        pixmap = self._cache.load(path, HOVER_PREVIEW_SIZE)
        if not pixmap.isNull():
            self._show(path, pixmap)
            return

        self._cache.prioritize([path])

    def _image_ready(self, path: str) -> None:
        if path != self._path or self._timer.isActive():
            return

        pixmap = self._cache.load(path, HOVER_PREVIEW_SIZE)
        if not pixmap.isNull():
            self._show(path, pixmap)

    def _show(self, path: str, pixmap: QPixmap) -> None:
        if path != self._path:
            return

        self._hide()
        preview = QLabel(None, Qt.WindowType.ToolTip)
        preview.setPixmap(pixmap)
        preview.setFrameShape(QFrame.Shape.Box)
        preview.setContentsMargins(4, 4, 4, 4)
        preview.adjustSize()
        preview.move(self._position + QPoint(16, 20))
        preview.show()
        self._preview = preview

    def _hide(self) -> None:
        if self._preview is None:
            return
        self._preview.close()
        self._preview.deleteLater()
        self._preview = None
