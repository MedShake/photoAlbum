from __future__ import annotations

from PySide6.QtCore import (
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
)

from photoalbum.rendering.fonts import (
    DEFAULT_MONOSPACE_FONT,
    resolve_font_family,
)

from .composition import GeographicWordCloud


def paint_geographic_word_cloud(
    painter: QPainter,
    *,
    target_rect,
    cloud: GeographicWordCloud,
    font_pixel_size,
) -> None:
    for word in cloud.words:
        rect = QRectF(
            (
                target_rect.x()
                + word.x
                * target_rect.width()
            ),
            (
                target_rect.y()
                + word.y
                * target_rect.height()
            ),
            (
                word.width
                * target_rect.width()
            ),
            (
                word.height
                * target_rect.height()
            ),
        )

        font = QFont(
            resolve_font_family(
                DEFAULT_MONOSPACE_FONT,
                fallback=DEFAULT_MONOSPACE_FONT,
            )
        )

        font.setBold(
            True
        )

        pixel_size = font_pixel_size(
            word.font_size_pt
        )

        font.setPixelSize(
            pixel_size
        )

        painter.setFont(
            font
        )

        painter.setPen(
            QColor(
                *word.color
            )
        )

        painter.drawText(
            rect,
            (
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            ),
            word.text,
        )
