from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFont,
    QPainter,
    QPen,
)


class PhotoPageWidgetRenderer:
    """
    Shared preview renderer for all built-in photo-page
    templates.

    The actual layout/capacity already belongs to the page
    composition, so photo-page-1/2/3/4 can use the same
    renderer.
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
        show_empty_slots: bool = True,
    ) -> None:
        if (
            composition is None
            or thumbnail_cache is None
            or pixel_rect is None
        ):
            return

        page = composition.page

        for index, slot in enumerate(
            composition.photo_slots
        ):
            if index >= len(page.photos):
                if show_empty_slots:
                    self._paint_empty_slot(
                        painter,
                        slot,
                        pixel_rect,
                    )
                continue

            photo = page.photos[index]

            self._paint_photo(
                painter,
                slot,
                photo.path,
                translator=translator,
                thumbnail_cache=thumbnail_cache,
                pixel_rect=pixel_rect,
            )

            self._paint_caption(
                painter,
                slot,
                font_pixel_size=font_pixel_size,
                pixel_rect=pixel_rect,
            )

    @staticmethod
    def _paint_photo(
        painter,
        slot,
        path,
        *,
        translator,
        thumbnail_cache,
        pixel_rect,
    ) -> None:
        rect = pixel_rect(
            slot.image_rect
        )

        pixmap = thumbnail_cache.load(
            path,
            rect.size(),
        )

        if pixmap.isNull():
            painter.setPen(
                QPen(
                    Qt.GlobalColor.gray,
                    1,
                )
            )

            painter.drawRect(
                rect
            )

            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                translator.tr(
                    "preview.image_unavailable"
                ),
            )
            return

        scaled = pixmap.scaled(
            rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = (
            rect.x()
            + (
                rect.width()
                - scaled.width()
            ) // 2
        )

        y = (
            rect.y()
            + (
                rect.height()
                - scaled.height()
            ) // 2
        )

        painter.drawPixmap(
            x,
            y,
            scaled,
        )

    @staticmethod
    def _paint_empty_slot(
        painter,
        slot,
        pixel_rect,
    ) -> None:
        rect = pixel_rect(
            slot.image_rect
        )

        painter.setPen(
            QPen(
                Qt.GlobalColor.lightGray,
                1,
                Qt.PenStyle.DashLine,
            )
        )

        painter.drawRect(
            rect
        )

    @staticmethod
    def _paint_caption(
        painter,
        slot,
        *,
        font_pixel_size,
        pixel_rect,
    ) -> None:
        if (
            slot.caption_rect is None
            or slot.caption.is_empty
        ):
            return

        rect = pixel_rect(
            slot.caption_rect
        )

        lines: list[str] = []

        if (
            slot.caption.capture_datetime
            is not None
        ):
            lines.append(
                slot.caption.capture_datetime.strftime(
                    "%d/%m/%Y %H:%M"
                )
            )

        if slot.caption.location_text:
            lines.append(
                slot.caption.location_text
            )

        font = QFont(
            painter.font()
        )

        font.setPixelSize(
            font_pixel_size(
                8
            )
        )

        painter.setFont(
            font
        )

        painter.setPen(
            Qt.GlobalColor.black
        )

        painter.drawText(
            rect,
            (
                Qt.AlignmentFlag.AlignHCenter
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap
            ),
            "\n".join(
                lines
            ),
        )
