from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import random
from typing import Callable, Iterable

from photoalbum.models import Photo

from .composition import NormalizedRect


@dataclass(frozen=True)
class CoverPeriod:
    first: datetime
    last: datetime

    @property
    def single_month(self) -> bool:
        return (
            self.first.year == self.last.year
            and self.first.month == self.last.month
        )

    @property
    def single_year(self) -> bool:
        return self.first.year == self.last.year


@dataclass(frozen=True)
class CoverScatterItem:
    photo: Photo
    rect: NormalizedRect


@dataclass(frozen=True)
class CoverScatterComposition:
    seed: int
    title: str
    items: tuple[CoverScatterItem, ...]


def cover_period(
    photos: Iterable[Photo],
) -> CoverPeriod | None:
    dates = sorted(
        photo.capture_datetime
        for photo in photos
        if photo.capture_datetime is not None
    )

    if not dates:
        return None

    return CoverPeriod(
        first=dates[0],
        last=dates[-1],
    )


def cover_period_title(
    photos: Iterable[Photo],
    month_name: Callable[[int], str],
) -> str:
    period = cover_period(photos)

    if period is None:
        return ""

    if period.single_month:
        month = month_name(
            period.first.month
        )

        if month:
            month = (
                month[:1].upper()
                + month[1:]
            )

        return (
            f"{month} "
            f"{period.first.year}"
        )

    if period.single_year:
        return str(
            period.first.year
        )

    return (
        f"{period.first.year}"
        f"–"
        f"{period.last.year}"
    )


def _display_dimensions(
    photo: Photo,
) -> tuple[int, int]:
    width = photo.width or 4
    height = photo.height or 3

    # EXIF orientations 5–8 swap displayed dimensions.
    if photo.orientation in (
        5,
        6,
        7,
        8,
    ):
        width, height = (
            height,
            width,
        )

    return width, height


def _photo_rect(
    rng: random.Random,
    photo: Photo,
) -> NormalizedRect:
    """
    Historical PHP cover geometry:

    - page: A4 portrait
    - margin: about 8 mm
    - landscape photos: max width about 32 mm
    - portrait photos: max height about 42 mm

    Overlap is intentional.
    """

    pixel_width, pixel_height = (
        _display_dimensions(photo)
    )

    ratio = (
        pixel_width
        / pixel_height
        if pixel_height > 0
        else 1.0
    )

    # Historical physical values normalized to A4.
    margin_x = 8.0 / 210.0
    margin_y = 8.0 / 297.0

    max_landscape_width = (
        32.0 / 210.0
    )

    max_portrait_height = (
        42.0 / 297.0
    )

    if ratio >= 1.0:
        width = max_landscape_width
        height = width / ratio
    else:
        height = max_portrait_height
        width = height * ratio

    maximum_x = (
        1.0
        - margin_x
        - width
    )

    maximum_y = (
        1.0
        - margin_y
        - height
    )

    x = rng.uniform(
        margin_x,
        max(
            margin_x,
            maximum_x,
        ),
    )

    y = rng.uniform(
        margin_y,
        max(
            margin_y,
            maximum_y,
        ),
    )

    return NormalizedRect(
        x=x,
        y=y,
        width=width,
        height=height,
    )


def compose_cover_scatter(
    photos: Iterable[Photo],
    *,
    seed: int,
    photo_count: int | None = None,
    month_name: Callable[[int], str],
) -> CoverScatterComposition:
    """
    Build the historical random stacked-photo cover.

    `photo_count` is retained for API/backward compatibility,
    but the classic built-in template deliberately uses ALL
    dated photos from the project.
    """

    eligible = [
        photo
        for photo in photos
        if photo.capture_datetime
        is not None
    ]

    eligible.sort(
        key=lambda photo: (
            photo.capture_datetime,
            photo.filename,
        )
    )

    title = cover_period_title(
        eligible,
        month_name,
    )

    rng = random.Random(seed)

    # Same spirit as PHP shuffle().
    shuffled = list(eligible)
    rng.shuffle(shuffled)

    items = tuple(
        CoverScatterItem(
            photo=photo,
            rect=_photo_rect(
                rng,
                photo,
            ),
        )
        for photo in shuffled
    )

    return CoverScatterComposition(
        seed=seed,
        title=title,
        items=items,
    )
