from __future__ import annotations

from PySide6.QtCore import (
    QRect,
    Qt,
)
from PySide6.QtGui import QPainter


class YearPhotoScatterRenderer:
    """
    Paint the photographic layer of a year-photo scatter.

    The composition owns placement/order.
    The renderer only converts normalized rectangles to pixels
    and paints the corresponding images.

    This renderer is usable by both preview and PDF export.
    """

    def paint(
        self,
        *,
        painter: QPainter,
        composition,
        target_rect: QRect,
        image_cache,
        **kwargs,
    ) -> None:
        width = target_rect.width()
        height = target_rect.height()

        for item in composition.items:
            rect = item.rect

            x = (
                target_rect.x()
                + round(rect.x * width)
            )
            y = (
                target_rect.y()
                + round(rect.y * height)
            )

            w = max(
                1,
                round(rect.width * width),
            )
            h = max(
                1,
                round(rect.height * height),
            )

            slot = QRect(
                x,
                y,
                w,
                h,
            )

            pixmap = image_cache.load(
                item.photo.path,
                slot.size(),
            )

            if pixmap.isNull():
                continue

            scaled = pixmap.scaled(
                slot.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            px = (
                slot.x()
                + (
                    slot.width()
                    - scaled.width()
                ) // 2
            )

            py = (
                slot.y()
                + (
                    slot.height()
                    - scaled.height()
                ) // 2
            )

            painter.drawPixmap(
                px,
                py,
                scaled,
            )
