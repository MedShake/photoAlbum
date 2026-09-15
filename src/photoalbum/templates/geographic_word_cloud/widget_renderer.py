from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter

from photoalbum.album import (
    A4,
    PageInstance,
)
from .painter import (
    paint_geographic_word_cloud,
)

from .composition import (
    compose_geographic_word_cloud,
)


class GeographicWordCloudWidgetRenderer:
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
    ) -> None:
        settings = instance.settings.get(
            "geographic_word_cloud",
            {},
        )

        if not isinstance(
            settings,
            dict,
        ):
            settings = {}

        year = settings.get(
            "year"
        )

        # Keep the historical A4 cloud geometry even when the
        # physical page is wider (for example US Letter).
        cloud = compose_geographic_word_cloud(
            list(photos),
            year=year,
            page_width_mm=A4.width_mm,
            page_height_mm=A4.height_mm,
        )

        paint_geographic_word_cloud(
            painter,
            target_rect=target_rect,
            cloud=cloud,
            font_pixel_size=font_pixel_size,
        )

        if not cloud.words:
            painter.setPen(
                Qt.GlobalColor.darkGray
            )

            painter.drawText(
                target_rect,
                Qt.AlignmentFlag.AlignCenter,
                translator.tr(
                    "page_settings.no_geographic_data"
                ),
            )
