from __future__ import annotations

from PySide6.QtCore import (
    QRectF,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFontMetricsF,
    QPainter,
)

from .composition import GeographicWordCloud
from .text_metrics import word_cloud_font


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

        font = word_cloud_font(
            word.font_size_pt
        )

        font.setPixelSize(
            font_pixel_size(
                word.font_size_pt
            )
        )

        painter.setFont(
            font
        )

        painter.setPen(
            QColor(
                *word.color
            )
        )

        metrics = QFontMetricsF(font)

        baseline_y = (
            rect.center().y()
            + (
                metrics.ascent()
                - metrics.descent()
            )
            / 2.0
        )

        painter.drawText(
            rect.left(),
            baseline_y,
            word.text,
        )
