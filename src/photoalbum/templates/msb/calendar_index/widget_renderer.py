from __future__ import annotations

from PySide6.QtGui import QPainter

from photoalbum.album import PageInstance
from photoalbum.templates.msb.calendar_index.painter import (
    paint_calendar_index,
)
from photoalbum.templates.msb.theme import (
    msb_theme_from_pack_settings,
)

from .composition import (
    calendar_month_page_numbers,
    compose_calendar_index,
)


class CalendarIndexWidgetRenderer:
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
        project_photos=None,
    ) -> None:
        photos = tuple(
            project_photos
            if project_photos is not None
            else photos
        )

        settings = instance.settings.get(
            "calendar_index",
            {},
        )

        if not isinstance(
            settings,
            dict,
        ):
            settings = {}

        years = sorted(
            {
                photo.capture_datetime.year
                for photo in photos
                if photo.capture_datetime
                is not None
            }
        )

        plan_year = None
        if composition is not None:
            page = getattr(composition, "page", None)
            plan_year = getattr(page, "year", None)

        year = (
            plan_year
            if plan_year in years
            else settings.get("year")
        )

        if year not in years:
            year = (
                years[0]
                if years
                else None
            )

        if year is None:
            return

        page_numbers = (
            calendar_month_page_numbers(
                album_pages,
                year,
            )
        )

        theme = msb_theme_from_pack_settings(
            template_pack_settings or {}
        )

        composition = compose_calendar_index(
            photos,
            year=year,
            month_page_numbers=page_numbers,
            month_colors=theme.month_colors,
        )

        paint_calendar_index(
            painter,
            target_rect=target_rect,
            composition=composition,
            translator=translator,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
        )
