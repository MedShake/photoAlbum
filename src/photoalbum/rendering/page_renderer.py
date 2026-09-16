from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QPainter

from photoalbum.rendering.fonts import resolve_font_family

from photoalbum.album.composition import PageComposition
from photoalbum.album.planning import PlanItemKind
from photoalbum.i18n import Translator
from photoalbum.template_engine import template_extension_registry


class PageRenderer:
    """
    Common QPainter renderer for an album page.

    It contains the rendering orchestration shared by the GUI
    preview and the future PDF exporter.

    Device-specific concerns remain injected by the caller:
    geometry, image cache and optional special-page render service.
    """

    def __init__(
        self,
        *,
        translator: Translator,
    ) -> None:
        self._translator = translator

    def paint(
        self,
        *,
        painter: QPainter,
        composition: PageComposition,
        target_rect: QRect,
        width: int,
        height: int,
        page_width_mm: float,
        page_height_mm: float,
        font_pixel_size: Callable[[float], int],
        pixel_rect: Callable,
        thumbnail_cache,
        project_photos=(),
        album_pages=(),
        render_service=None,
        set_waiting_key=None,
        paint_fallback=None,
        show_empty_slots: bool = True,
    ) -> None:
        page = composition.page

        rendered = False

        if (
            page.kind == PlanItemKind.SPECIAL_PAGE
            and page.page_instance is not None
        ):
            rendered = self._paint_special_page(
                painter=painter,
                composition=composition,
                target_rect=target_rect,
                width=width,
                height=height,
                page_width_mm=page_width_mm,
                page_height_mm=page_height_mm,
                font_pixel_size=font_pixel_size,
                project_photos=project_photos,
                album_pages=album_pages,
                render_service=render_service,
                set_waiting_key=set_waiting_key,
                thumbnail_cache=thumbnail_cache,
            )

        elif page.kind in (
            PlanItemKind.PHOTO_GROUP,
            PlanItemKind.MONTH_DIVIDER,
            PlanItemKind.YEAR_DIVIDER,
        ):
            rendered = self._paint_template_page(
                painter=painter,
                composition=composition,
                target_rect=target_rect,
                width=width,
                height=height,
                page_width_mm=page_width_mm,
                page_height_mm=page_height_mm,
                font_pixel_size=font_pixel_size,
                pixel_rect=pixel_rect,
                thumbnail_cache=thumbnail_cache,
                album_pages=album_pages,
                render_service=render_service,
                set_waiting_key=set_waiting_key,
                show_empty_slots=show_empty_slots,
            )

        if not rendered and paint_fallback is not None:
            paint_fallback(
                painter
            )

        self._paint_page_number(
            painter=painter,
            composition=composition,
            font_pixel_size=font_pixel_size,
            pixel_rect=pixel_rect,
        )

    def _paint_special_page(
        self,
        *,
        painter,
        composition,
        target_rect,
        width,
        height,
        page_width_mm,
        page_height_mm,
        font_pixel_size,
        project_photos,
        album_pages,
        render_service,
        set_waiting_key,
        thumbnail_cache,
    ) -> bool:
        instance = composition.page.page_instance

        if instance is None:
            return False

        extension = template_extension_registry.get(
            instance.template_id
        )

        renderer = (
            extension.widget_renderer
            if extension is not None
            else None
        )

        if renderer is None:
            return False

        renderer.paint(
            painter=painter,
            instance=instance,
            photos=project_photos,
            target_rect=target_rect,
            width=width,
            height=height,
            translator=self._translator,
            render_service=render_service,
            set_waiting_key=set_waiting_key,
            font_pixel_size=font_pixel_size,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            album_pages=album_pages,
            thumbnail_cache=thumbnail_cache,
        )

        return True

    def _paint_template_page(
        self,
        *,
        painter,
        composition,
        target_rect,
        width,
        height,
        page_width_mm,
        page_height_mm,
        font_pixel_size,
        pixel_rect,
        thumbnail_cache,
        album_pages,
        render_service,
        set_waiting_key,
        show_empty_slots,
    ) -> bool:
        page = composition.page

        extension = template_extension_registry.get(
            page.template_id
        )

        renderer = (
            extension.widget_renderer
            if extension is not None
            else None
        )

        if renderer is None:
            return False

        paint_kwargs = dict(
            painter=painter,
            instance=page.page_instance,
            photos=page.photos,
            target_rect=target_rect,
            width=width,
            height=height,
            translator=self._translator,
            render_service=render_service,
            set_waiting_key=set_waiting_key,
            font_pixel_size=font_pixel_size,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            album_pages=album_pages,
            composition=composition,
            thumbnail_cache=thumbnail_cache,
            pixel_rect=pixel_rect,
        )

        # Empty slots only concern photo-page renderers.
        # Other template renderers must keep their existing
        # paint() contract.
        if composition.photo_slots:
            paint_kwargs["show_empty_slots"] = (
                show_empty_slots
            )

        renderer.paint(
            **paint_kwargs
        )

        return True

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
