from __future__ import annotations

from PySide6.QtGui import QPainter

from photoalbum.album import PageInstance
from photoalbum.templates.calendar_index.painter import (
    paint_calendar_index,
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
    ) -> None:
        photos = tuple(
            photos
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

        year = settings.get(
            "year"
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

        composition = compose_calendar_index(
            photos,
            year=year,
            month_page_numbers=page_numbers,
        )

        paint_calendar_index(
            painter,
            target_rect=target_rect,
            composition=composition,
            translator=translator,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
        )
