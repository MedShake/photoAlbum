from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter

from photoalbum.album import PageInstance

from .composition import compose_geographic_map
from .rendering import paint_map, render_options


class GeographicMapWidgetRenderer:
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
        **kwargs,
    ) -> None:
        photos = tuple(photos)

        settings = instance.settings.get(
            "geographic_map",
            {},
        )

        if not isinstance(settings, dict):
            settings = {}

        if render_service is not None:
            effective_photos = (
                render_service.effective_photos(
                    instance,
                    photos,
                )
            )

            key = render_service.key_for(
                instance,
                effective_photos,
                width=width,
                height=height,
                page_width_mm=page_width_mm,
                page_height_mm=page_height_mm,
                template_pack_settings=template_pack_settings,
            )

            if set_waiting_key is not None:
                set_waiting_key(
                    key
                )

            pixmap = render_service.cached(
                key
            )

            if pixmap is None:
                render_service.request(
                    instance,
                    effective_photos,
                    width=width,
                    height=height,
                    page_width_mm=page_width_mm,
                    page_height_mm=page_height_mm,
                    template_pack_settings=template_pack_settings,
                )

                painter.setPen(
                    Qt.GlobalColor.darkGray
                )

                painter.drawText(
                    target_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    translator.tr(
                        "page_settings.calculating"
                    ),
                )

                return

            painter.drawPixmap(
                target_rect,
                pixmap,
                pixmap.rect(),
            )

            return

        # Synchronous vector path used by final rendering.
        map_composition = compose_geographic_map(
            list(photos),
            year=settings.get("year"),
        )

        paint_map(
            painter, target_rect, map_composition,
            **render_options(settings, translator, template_pack_settings),
        )
