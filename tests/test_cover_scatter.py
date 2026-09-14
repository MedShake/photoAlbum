from datetime import datetime
from pathlib import Path

from photoalbum.album.cover_scatter import (
    compose_cover_scatter,
    cover_period_title,
)
from photoalbum.models import Photo


def photo(
    name: str,
    year: int,
    month: int,
    day: int,
) -> Photo:
    return Photo(
        path=Path("/photos") / name,
        filename=name,
        capture_datetime=datetime(
            year,
            month,
            day,
        ),
        width=4000,
        height=3000,
    )


def month_name(month: int) -> str:
    return {
        3: "mars",
        4: "avril",
    }.get(month, str(month))


def test_single_month_title():
    photos = [
        photo("a.jpg", 2025, 3, 1),
        photo("b.jpg", 2025, 3, 20),
    ]

    assert (
        cover_period_title(
            photos,
            month_name,
        )
        == "Mars 2025"
    )


def test_single_year_title():
    photos = [
        photo("a.jpg", 2025, 3, 1),
        photo("b.jpg", 2025, 4, 20),
    ]

    assert (
        cover_period_title(
            photos,
            month_name,
        )
        == "2025"
    )


def test_multi_year_title():
    photos = [
        photo("a.jpg", 2024, 3, 1),
        photo("b.jpg", 2026, 4, 20),
    ]

    assert (
        cover_period_title(
            photos,
            month_name,
        )
        == "2024–2026"
    )


def test_same_seed_is_reproducible():
    photos = [
        photo(
            f"{index}.jpg",
            2025,
            3,
            index + 1,
        )
        for index in range(10)
    ]

    first = compose_cover_scatter(
        photos,
        seed=12345,
        photo_count=6,
        month_name=month_name,
    )

    second = compose_cover_scatter(
        photos,
        seed=12345,
        photo_count=6,
        month_name=month_name,
    )

    assert first == second


def test_different_seed_changes_proposal():
    photos = [
        photo(
            f"{index}.jpg",
            2025,
            3,
            index + 1,
        )
        for index in range(10)
    ]

    first = compose_cover_scatter(
        photos,
        seed=1,
        photo_count=6,
        month_name=month_name,
    )

    second = compose_cover_scatter(
        photos,
        seed=2,
        photo_count=6,
        month_name=month_name,
    )

    assert first != second


def test_classic_cover_uses_all_dated_photos():
    photos = [
        photo(
            f"{index}.jpg",
            2025,
            3,
            index + 1,
        )
        for index in range(10)
    ]

    composition = compose_cover_scatter(
        photos,
        seed=123,
        photo_count=4,
        month_name=month_name,
    )

    # The classic built-in cover deliberately reproduces
    # the historical PHP behavior: every dated photo is used.
    assert len(composition.items) == 10
