from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import (
    QPixmap,
)

from .image_loader import load_qimage


class RenderImageCache:
    """
    Image cache shared by preview and final rendering.

    Images are retained close to the requested target size. The image service
    can also reduce JPEG decoding; HEIF currently needs a full source decode.

    The image service applies orientation and normalizes colors to sRGB.
    """

    def __init__(self) -> None:
        self._cache: dict[
            tuple[str, int, int],
            QPixmap,
        ] = {}

        self._source_signatures: dict[str, tuple[int, int] | None] = {}

    @staticmethod
    def _source_signature(path: str) -> tuple[int, int] | None:
        try:
            stat = Path(path).stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def clear(self) -> None:
        self._cache.clear()
        self._source_signatures.clear()

    def invalidate_changed_sources(self) -> None:
        """Check once per source on album refresh, never on every paint.

        Keep all requested sizes for unchanged files. Like the scanner,
        use file modification time and size to detect replaced images.
        """
        changed = {
            path for path, signature in self._source_signatures.items()
            if self._source_signature(path) != signature
        }
        if not changed:
            return
        for key in list(self._cache):
            if key[0] in changed:
                del self._cache[key]
        for path in changed:
            del self._source_signatures[path]

    def load(
        self,
        path: str | Path,
        target_size: QSize,
    ) -> QPixmap:
        path = str(path)

        key = (
            path,
            target_size.width(),
            target_size.height(),
        )

        cached = self._cache.get(key)

        if cached is not None:
            return cached

        if path not in self._source_signatures:
            self._source_signatures[path] = self._source_signature(path)
        maximum = max(target_size.width(), target_size.height())
        image = load_qimage(path, QSize(maximum, maximum))

        if image.isNull():
            pixmap = QPixmap()
        else:
            pixmap = QPixmap.fromImage(
                image
            )

        self._cache[key] = pixmap

        return pixmap
