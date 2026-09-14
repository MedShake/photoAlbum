from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter

from photoalbum.album import PageInstance
from photoalbum.gui.geographic_word_cloud_painter import (
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

        cloud = compose_geographic_word_cloud(
            list(photos),
            year=year,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
        )

        paint_geographic_word_cloud(
            painter,
            target_rect=target_rect,
            cloud=cloud,
            page_width_mm=page_width_mm,
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
