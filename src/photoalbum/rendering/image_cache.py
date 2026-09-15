from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QImageReader,
    QPixmap,
)


class RenderImageCache:
    """
    Image cache shared by preview and final rendering.

    Images are decoded close to the requested target size instead
    of decoding the full camera image unnecessarily.

    EXIF orientation is applied by QImageReader.
    """

    def __init__(self) -> None:
        self._cache: dict[
            tuple[str, int, int],
            QPixmap,
        ] = {}

    def clear(self) -> None:
        self._cache.clear()

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

        reader = QImageReader(path)
        reader.setAutoTransform(True)

        source_size = reader.size()

        if source_size.isValid():
            maximum = max(
                target_size.width(),
                target_size.height(),
            )

            decode_size = source_size.scaled(
                QSize(
                    maximum,
                    maximum,
                ),
                Qt.AspectRatioMode.KeepAspectRatio,
            )

            if decode_size.isValid():
                reader.setScaledSize(
                    decode_size
                )

        image = reader.read()

        if image.isNull():
            pixmap = QPixmap()
        else:
            pixmap = QPixmap.fromImage(
                image
            )

        self._cache[key] = pixmap

        return pixmap
