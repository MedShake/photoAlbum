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

from photoalbum.album.geographic_word_cloud import (
    GeographicWordCloud,
)


def paint_geographic_word_cloud(
    painter: QPainter,
    *,
    target_rect,
    cloud: GeographicWordCloud,
    page_width_mm: float,
    font_pixel_size=None,
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
            "Courier"
        )

        font.setBold(
            True
        )

        if font_pixel_size is not None:
            pixel_size = font_pixel_size(
                word.font_size_pt
            )
        else:
            # Compatibility path for callers that do not yet
            # provide the shared physical font converter.
            font_mm = (
                word.font_size_pt
                * 25.4
                / 72.0
            )

            pixel_size = max(
                5,
                round(
                    font_mm
                    * target_rect.width()
                    / page_width_mm
                ),
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
