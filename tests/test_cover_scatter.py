import pytest
from datetime import datetime
from pathlib import Path

from photoalbum.templates.msb.year_photo_scatter.composition import (
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
        month_name=month_name,
    )

    second = compose_cover_scatter(
        photos,
        seed=12345,
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
        month_name=month_name,
    )

    second = compose_cover_scatter(
        photos,
        seed=2,
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
        month_name=month_name,
    )

    # The classic built-in cover deliberately reproduces
    # the historical PHP behavior: every dated photo is used.
    assert len(composition.items) == 10


def test_completely_hidden_photo_is_removed():
    from photoalbum.album.composition import NormalizedRect
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        CoverScatterItem,
        visible_cover_scatter_items,
    )

    bottom = photo(
        "bottom.jpg",
        2025,
        3,
        1,
    )
    top = photo(
        "top.jpg",
        2025,
        3,
        2,
    )

    rect = NormalizedRect(
        x=0.1,
        y=0.1,
        width=0.3,
        height=0.3,
    )

    items = (
        CoverScatterItem(bottom, rect),
        CoverScatterItem(top, rect),
    )

    visible = visible_cover_scatter_items(
        items
    )

    assert visible == (
        items[1],
    )


def test_partially_visible_photo_is_kept():
    from photoalbum.album.composition import NormalizedRect
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        CoverScatterItem,
        visible_cover_scatter_items,
    )

    bottom = photo(
        "bottom.jpg",
        2025,
        3,
        1,
    )
    top = photo(
        "top.jpg",
        2025,
        3,
        2,
    )

    items = (
        CoverScatterItem(
            bottom,
            NormalizedRect(
                0.1,
                0.1,
                0.4,
                0.4,
            ),
        ),
        CoverScatterItem(
            top,
            NormalizedRect(
                0.2,
                0.2,
                0.2,
                0.2,
            ),
        ),
    )

    assert (
        visible_cover_scatter_items(
            items
        )
        == items
    )


def test_png_is_not_used_as_opaque_occluder():
    from photoalbum.album.composition import NormalizedRect
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        CoverScatterItem,
        visible_cover_scatter_items,
    )

    bottom = photo(
        "bottom.jpg",
        2025,
        3,
        1,
    )

    png = photo(
        "overlay.png",
        2025,
        3,
        2,
    )

    rect = NormalizedRect(
        0.1,
        0.1,
        0.3,
        0.3,
    )

    items = (
        CoverScatterItem(bottom, rect),
        CoverScatterItem(png, rect),
    )

    assert (
        visible_cover_scatter_items(
            items
        )
        == items
    )


def test_scatter_physical_sizes_follow_page_format():
    photos = [
        photo(
            "landscape.jpg",
            2025,
            3,
            1,
        )
    ]

    a4 = compose_cover_scatter(
        photos,
        seed=123,
        month_name=month_name,
        page_width_mm=210.0,
        page_height_mm=297.0,
    )

    letter = compose_cover_scatter(
        photos,
        seed=123,
        month_name=month_name,
        page_width_mm=215.9,
        page_height_mm=279.4,
    )

    assert len(a4.items) == 1
    assert len(letter.items) == 1

    a4_rect = a4.items[0].rect
    letter_rect = letter.items[0].rect

    # The normalized geometry changes with the paper size,
    # but the resulting physical dimensions remain constant.
    assert a4_rect.width != letter_rect.width

    assert (
        a4_rect.width * 210.0
        == pytest.approx(
            letter_rect.width * 215.9
        )
    )

    assert (
        a4_rect.height * 297.0
        == pytest.approx(
            letter_rect.height * 279.4
        )
    )
