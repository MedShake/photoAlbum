from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from photoalbum.models import Photo

from photoalbum.album.planning import PlanItemKind


from photoalbum.templates.msb.theme import (
    DEFAULT_MONTH_COLORS,
)


@dataclass(frozen=True)
class CalendarDay:
    day: int | None
    has_photo: bool = False


@dataclass(frozen=True)
class CalendarWeek:
    week_number: int
    days: tuple[CalendarDay, ...]


@dataclass(frozen=True)
class CalendarMonth:
    month: int
    page_number: int | None
    color: tuple[int, int, int]
    weeks: tuple[CalendarWeek, ...]


@dataclass(frozen=True)
class CalendarIndexComposition:
    year: int
    months: tuple[CalendarMonth, ...]


def available_calendar_years(
    photos,
) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                photo.capture_datetime.year
                for photo in photos
                if photo.capture_datetime
                is not None
            }
        )
    )


def calendar_month_page_numbers(
    pages,
    year: int,
) -> dict[int, int]:
    result: dict[int, int] = {}

    for page in pages:
        if (
            page.kind
            == PlanItemKind.MONTH_DIVIDER
            and page.year == year
            and page.month is not None
        ):
            result.setdefault(
                page.month,
                page.number,
            )

    return result


def compose_calendar_index(
    photos,
    *,
    year: int,
    month_page_numbers: dict[int, int] | None = None,
    month_colors: dict[int, tuple[int, int, int]] | None = None,
) -> CalendarIndexComposition:
    month_page_numbers = (
        month_page_numbers or {}
    )
    month_colors = (
        month_colors or DEFAULT_MONTH_COLORS
    )

    photo_dates: set[date] = {
        photo.capture_datetime.date()
        for photo in photos
        if (
            photo.capture_datetime
            is not None
            and photo.capture_datetime.year
            == year
        )
    }

    cal = calendar.Calendar(
        firstweekday=calendar.MONDAY
    )

    months = []

    for month in range(1, 13):
        weeks = []

        for raw_week in cal.monthdatescalendar(
            year,
            month,
        ):
            # PHP displayed the ISO week number belonging to
            # the current row of the month.
            in_month = [
                value
                for value in raw_week
                if value.month == month
            ]

            reference = (
                in_month[0]
                if in_month
                else raw_week[0]
            )

            days = tuple(
                CalendarDay(
                    day=(
                        value.day
                        if value.month == month
                        else None
                    ),
                    has_photo=(
                        value in photo_dates
                        if value.month == month
                        else False
                    ),
                )
                for value in raw_week
            )

            weeks.append(
                CalendarWeek(
                    week_number=(
                        reference.isocalendar().week
                    ),
                    days=days,
                )
            )

        months.append(
            CalendarMonth(
                month=month,
                page_number=(
                    month_page_numbers.get(
                        month
                    )
                ),
                color=month_colors[month],
                weeks=tuple(weeks),
            )
        )

    return CalendarIndexComposition(
        year=year,
        months=tuple(months),
    )
