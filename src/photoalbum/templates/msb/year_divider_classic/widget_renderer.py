from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
)

from photoalbum.rendering.fonts import resolve_font_family

from photoalbum.album import PageInstance


class YearDividerClassicWidgetRenderer:
    """
    Classic year divider.

    Displays the year centered on the page using the same
    typographic size as a single-year year-photo-scatter title.
    """

    DEFAULT_TITLE_COLOR = "#d0d0d0"

    @classmethod
    def _title_color(
        cls,
        instance: PageInstance,
    ) -> QColor:
        settings = instance.settings.get(
            "year_divider",
            {},
        )

        if not isinstance(settings, dict):
            settings = {}

        color = QColor(
            str(
                settings.get(
                    "title_color",
                    cls.DEFAULT_TITLE_COLOR,
                )
            )
        )

        if not color.isValid():
            return QColor(
                cls.DEFAULT_TITLE_COLOR
            )

        return color

    def paint(
        self,
        *,
        painter: QPainter,
        instance: PageInstance,
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
            template_pack_settings=None,
) -> None:
        year = ""

        if composition is not None:
            page = getattr(
                composition,
                "page",
                None,
            )

            value = getattr(
                page,
                "year",
                None,
            )

            if value is not None:
                year = str(value)

        font = QFont(
            resolve_font_family(None)
        )
        font.setBold(True)
        font.setPixelSize(
            font_pixel_size(72)
        )

        painter.setFont(font)
        painter.setPen(
            self._title_color(instance)
        )

        painter.drawText(
            target_rect.adjusted(
                15,
                15,
                -15,
                -15,
            ),
            Qt.AlignmentFlag.AlignCenter,
            year,
        )
