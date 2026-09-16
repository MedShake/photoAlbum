from datetime import datetime
from pathlib import Path

from photoalbum.templates.msb.calendar_index.composition import (
    available_calendar_years,
    compose_calendar_index,
)
from photoalbum.models import Photo


def photo(
    name: str,
    year: int,
    month: int,
    day: int,
) -> Photo:
    return Photo(
        path=Path(name),
        filename=name,
        capture_datetime=datetime(
            year,
            month,
            day,
        ),
    )


def test_available_years():
    photos = [
        photo("a.jpg", 2024, 1, 1),
        photo("b.jpg", 2025, 1, 1),
        photo("c.jpg", 2025, 2, 1),
    ]

    assert available_calendar_years(
        photos
    ) == (
        2024,
        2025,
    )


def test_calendar_contains_twelve_months():
    composition = compose_calendar_index(
        [],
        year=2025,
    )

    assert len(
        composition.months
    ) == 12


def test_photo_date_is_highlighted():
    composition = compose_calendar_index(
        [
            photo(
                "photo.jpg",
                2025,
                3,
                14,
            )
        ],
        year=2025,
    )

    march = composition.months[2]

    highlighted = [
        day.day
        for week in march.weeks
        for day in week.days
        if day.has_photo
    ]

    assert highlighted == [14]


def test_other_year_is_not_highlighted():
    composition = compose_calendar_index(
        [
            photo(
                "photo.jpg",
                2024,
                3,
                14,
            )
        ],
        year=2025,
    )

    assert not any(
        day.has_photo
        for month in composition.months
        for week in month.weeks
        for day in week.days
    )


def test_month_page_number_is_preserved():
    composition = compose_calendar_index(
        [],
        year=2025,
        month_page_numbers={
            3: 17,
        },
    )

    assert (
        composition.months[2].page_number
        == 17
    )
