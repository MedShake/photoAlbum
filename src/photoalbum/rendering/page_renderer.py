from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter

from photoalbum.album.composition import PageComposition
from photoalbum.rendering.fonts import resolve_font_family
from photoalbum.rendering.temporal_context import materialized_periods
from photoalbum.template_engine import template_extension_registry, translator_for_template
from photoalbum.template_engine.instances import create_template_instance


class PageRenderer:
    """One template rendering contract for settings previews, album previews and PDF."""

    def __init__(self, *, translator):
        self._translator = translator

    def paint_template(
        self, *, instance, painter, target_rect, width, height,
        page_width_mm, page_height_mm, font_pixel_size,
        photos=(), project_photos=None, composition=None,
        pixel_rect=None, thumbnail_cache=None, album_pages=(),
        template_pack_settings=None, render_service=None,
        set_waiting_key=None, show_empty_slots=True, temporal_context=None,
    ) -> bool:
        if instance is None:
            return False
        extension = template_extension_registry.get(instance.template_id)
        if extension is None or extension.widget_renderer is None:
            return False
        project_photos = photos if project_photos is None else project_photos
        extension.widget_renderer.paint(
            painter=painter, instance=instance,
            photos=project_photos if extension.photo_scope == "album" else photos,
            project_photos=project_photos, composition=composition,
            target_rect=target_rect, width=width, height=height,
            page_width_mm=page_width_mm, page_height_mm=page_height_mm,
            font_pixel_size=font_pixel_size, pixel_rect=pixel_rect,
            thumbnail_cache=thumbnail_cache, album_pages=album_pages,
            template_pack_settings=template_pack_settings or {},
            translator=translator_for_template(instance.template_id, self._translator),
            render_service=render_service, set_waiting_key=set_waiting_key,
            show_empty_slots=show_empty_slots,
            temporal_context=(materialized_periods(getattr(composition, "page", None), album_pages)
                              if temporal_context is None else temporal_context),
        )
        return True

    def paint(
        self, *, painter, composition, target_rect, width, height,
        page_width_mm, page_height_mm, font_pixel_size, pixel_rect,
        thumbnail_cache, project_photos=(), album_pages=(),
        template_pack_settings=None, render_service=None,
        set_waiting_key=None, paint_fallback=None, show_empty_slots=True,
        temporal_context=None,
    ) -> None:
        page = composition.page
        instance = page.page_instance
        if instance is None and page.template_id is not None:
            instance = create_template_instance(page.template_id)
        rendered = self.paint_template(
            instance=instance, painter=painter, composition=composition,
            target_rect=target_rect, width=width, height=height,
            page_width_mm=page_width_mm, page_height_mm=page_height_mm,
            font_pixel_size=font_pixel_size, pixel_rect=pixel_rect,
            photos=page.photos, project_photos=project_photos,
            thumbnail_cache=thumbnail_cache, album_pages=album_pages,
            template_pack_settings=template_pack_settings,
            render_service=render_service, set_waiting_key=set_waiting_key,
            show_empty_slots=show_empty_slots, temporal_context=temporal_context,
        )
        if not rendered and paint_fallback is not None:
            paint_fallback(painter)
        self._paint_page_number(
            painter=painter, composition=composition,
            font_pixel_size=font_pixel_size, pixel_rect=pixel_rect,
        )

    @staticmethod
    def _paint_page_number(
        *,
        painter: QPainter,
        composition: PageComposition,
        font_pixel_size,
        pixel_rect,
    ) -> None:
        page_number = composition.page_number

        if page_number is None:
            return

        rect = pixel_rect(
            page_number.rect
        )

        # Avoid importing GUI preview code just for this enum.
        alignment_value = getattr(
            page_number.alignment,
            "value",
            page_number.alignment,
        )

        if alignment_value == "left":
            alignment = Qt.AlignmentFlag.AlignLeft
        else:
            alignment = Qt.AlignmentFlag.AlignRight

        font = QFont(
            resolve_font_family(None)
        )

        font.setBold(
            False
        )

        font.setPixelSize(
            font_pixel_size(8)
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
                alignment
                | Qt.AlignmentFlag.AlignVCenter
            ),
            str(page_number.number),
        )
