from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
)

from photoalbum.album.month_divider_layout import (
    CLASSIC_MONTH_DIVIDER_LAYOUT,
)


class MonthDividerClassicWidgetRenderer:
    """
    Preview renderer for the classic month divider.

    All visual rules of this template live here rather than
    inside AlbumPreviewWidget.
    """

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
        if (
            composition is None
            or pixel_rect is None
        ):
            return

        page = composition.page

        if (
            page.year is None
            or page.month is None
        ):
            return

        layout = (
            CLASSIC_MONTH_DIVIDER_LAYOUT
        )

        month_name = (
            translator.month_name(
                page.month
            )
        )

        if month_name:
            month_name = (
                month_name[:1].upper()
                + month_name[1:]
            )

        title = (
            f"{month_name} {page.year}"
        )

        red, green, blue = (
            layout.color_for_month(
                page.month
            )
        )

        painter.setPen(
            QColor(
                red,
                green,
                blue,
            )
        )

        font = QFont(
            painter.font()
        )

        font.setBold(
            True
        )

        font.setPixelSize(
            font_pixel_size(
                layout.title_font_pt
            )
        )

        painter.setFont(
            font
        )

        painter.drawText(
            pixel_rect(
                layout.title_rect
            ),
            (
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
            title,
        )

        if not page.cities:
            return

        painter.setPen(
            Qt.GlobalColor.black
        )

        font = QFont(
            painter.font()
        )

        font.setBold(
            False
        )

        font.setPixelSize(
            font_pixel_size(
                layout.cities_font_pt
            )
        )

        painter.setFont(
            font
        )

        painter.drawText(
            pixel_rect(
                layout.cities_rect
            ),
            (
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap
            ),
            "\n".join(
                page.cities
            ),
        )
