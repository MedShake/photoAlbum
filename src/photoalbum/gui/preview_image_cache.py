"""Asynchronous, resolution-stable images for the interactive album preview."""
from __future__ import annotations

from math import ceil
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QImage, QImageReader, QPixmap

from photoalbum.rendering.image_cache import RenderImageCache


class _Signals(QObject):
    finished = Signal(object, QImage)


class _Decode(QRunnable):
    def __init__(self, token, path, edge):
        super().__init__()
        self.token, self.path, self.edge = token, path, edge
        self.signals = _Signals()

    def run(self):
        image = QImage()
        try:
            reader = QImageReader(self.path)
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid() and max(size.width(), size.height()) > self.edge:
                reader.setScaledSize(size.scaled(
                    QSize(self.edge, self.edge), Qt.AspectRatioMode.KeepAspectRatio,
                ))
            image = reader.read()
        except Exception:
            image = QImage()
        finally:
            try:
                self.signals.finished.emit(self.token, image)
            except RuntimeError:
                # The owning preview may have been destroyed during decoding.
                pass


class PreviewImageCache(QObject):
    ready = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._edge = 778
        self._cache = {}  # path -> (decoded edge, pixmap)
        self._signatures = {}
        self._versions = {}
        self._generation = 0
        self._queue = {}  # ordered, replaceable viewport priorities
        self._active = {}
        self._pool = QThreadPool.globalInstance()

    def set_resolution(self, maximum_width, maximum_height, density):
        self._edge = max(1, ceil(max(maximum_width, maximum_height) * density))

    def clear(self):
        self._generation += 1
        self._cache.clear()
        self._signatures.clear()
        self._versions.clear()
        self._queue.clear()

    def invalidate_changed_sources(self):
        for path, signature in list(self._signatures.items()):
            current = RenderImageCache._source_signature(path)
            if current != signature:
                self._cache.pop(path, None)
                self._versions[path] = self._versions.get(path, 0) + 1
                self._signatures[path] = current

    def _token(self, path):
        return (self._generation, path, self._versions.get(path, 0), self._edge)

    def _needed(self, path):
        cached = self._cache.get(path)
        return cached is None or cached[0] < self._edge

    def prioritize(self, paths):
        # Running jobs finish; obsolete queued work never reaches the pool.
        self._queue = {str(path): None for path in paths if self._needed(str(path))}
        self._start_next()

    def is_loading(self, path: str | Path) -> bool:
        return str(path) not in self._cache

    def load(self, path: str | Path, target_size: QSize) -> QPixmap:
        # Painting performs no I/O or decoding. Viewport scheduling owns requests.
        cached = self._cache.get(str(path))
        return cached[1] if cached is not None else QPixmap()

    def _start_next(self):
        for path in list(self._queue):
            if len(self._active) >= 2:
                break
            token = self._token(path)
            if token in self._active:
                continue
            del self._queue[path]
            if not self._needed(path):
                continue
            if path not in self._signatures:
                self._signatures[path] = RenderImageCache._source_signature(path)
            worker = _Decode(token, path, self._edge)
            worker.signals.finished.connect(self._finished)
            self._active[token] = worker
            self._pool.start(worker)

    @Slot(object, QImage)
    def _finished(self, token, image):
        self._active.pop(token, None)
        generation, path, version, edge = token
        if generation == self._generation and version == self._versions.get(path, 0):
            previous = self._cache.get(path)
            if previous is None or previous[0] <= edge:
                self._cache[path] = (edge, QPixmap.fromImage(image))
                self.ready.emit(path)
        self._start_next()
