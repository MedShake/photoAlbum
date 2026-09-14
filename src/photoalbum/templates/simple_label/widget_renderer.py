from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFont,
    QPainter,
)


class SimpleLabelWidgetRenderer:
    """
    Renderer for templates whose current preview is only a
    centered translated label.

    This preserves the historical AlbumPreviewWidget fallback
    while moving template-specific choices out of the core.
    """

    def __init__(
        self,
        translation_key: str,
    ) -> None:
        self._translation_key = (
            translation_key
        )

    def paint(
        self,
        *,
        painter: QPainter,
        instance,
        photos,
        target_rect,
        width: int,
        height: int,
        translator,
        render_service,
        set_waiting_key,
        font_pixel_size,
        page_width_mm: float = 210.0,
        page_height_mm: float = 297.0,
        album_pages=(),
        composition=None,
        thumbnail_cache=None,
        pixel_rect=None,
    ) -> None:
        painter.setPen(
            Qt.GlobalColor.darkGray
        )

        font = QFont(
            painter.font()
        )

        font.setBold(
            True
        )

        font.setPixelSize(
            font_pixel_size(
                14
            )
        )

        painter.setFont(
            font
        )

        painter.drawText(
            target_rect.adjusted(
                20,
                20,
                -20,
                -20,
            ),
            Qt.AlignmentFlag.AlignCenter,
            translator.tr(
                self._translation_key
            ),
        )
