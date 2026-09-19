from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter

from photoalbum.album import (
    PageInstance,
)
from .painter import (
    paint_geographic_word_cloud,
)
from photoalbum.templates.msb.theme import (
    msb_theme_from_pack_settings,
    palette_from_settings,
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
        template_pack_settings=None,
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

        theme = msb_theme_from_pack_settings(
            template_pack_settings or {}
        )

        palette_colors = palette_from_settings(
            settings.get("palette"),
            fallback=theme.month_colors,
        )

        palette = tuple(
            palette_colors[month]
            for month in range(1, 13)
        )

        cloud = compose_geographic_word_cloud(
            list(photos),
            year=year,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            palette=palette,
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
