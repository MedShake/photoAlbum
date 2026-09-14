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



def _rect_intersection(
    first: NormalizedRect,
    second: NormalizedRect,
) -> NormalizedRect | None:
    left = max(first.x, second.x)
    top = max(first.y, second.y)

    right = min(
        first.x + first.width,
        second.x + second.width,
    )
    bottom = min(
        first.y + first.height,
        second.y + second.height,
    )

    if right <= left or bottom <= top:
        return None

    return NormalizedRect(
        x=left,
        y=top,
        width=right - left,
        height=bottom - top,
    )


def _subtract_rect(
    source: NormalizedRect,
    cover: NormalizedRect,
) -> tuple[NormalizedRect, ...]:
    """
    Remove an axis-aligned opaque rectangle from another one.

    The remaining area is represented by at most four
    non-overlapping rectangles.
    """

    intersection = _rect_intersection(
        source,
        cover,
    )

    if intersection is None:
        return (source,)

    pieces: list[NormalizedRect] = []

    source_right = (
        source.x + source.width
    )
    source_bottom = (
        source.y + source.height
    )

    intersection_right = (
        intersection.x
        + intersection.width
    )
    intersection_bottom = (
        intersection.y
        + intersection.height
    )

    # Top strip.
    if intersection.y > source.y:
        pieces.append(
            NormalizedRect(
                x=source.x,
                y=source.y,
                width=source.width,
                height=(
                    intersection.y
                    - source.y
                ),
            )
        )

    # Bottom strip.
    if intersection_bottom < source_bottom:
        pieces.append(
            NormalizedRect(
                x=source.x,
                y=intersection_bottom,
                width=source.width,
                height=(
                    source_bottom
                    - intersection_bottom
                ),
            )
        )

    middle_top = intersection.y
    middle_height = intersection.height

    # Left strip inside intersection height.
    if intersection.x > source.x:
        pieces.append(
            NormalizedRect(
                x=source.x,
                y=middle_top,
                width=(
                    intersection.x
                    - source.x
                ),
                height=middle_height,
            )
        )

    # Right strip inside intersection height.
    if intersection_right < source_right:
        pieces.append(
            NormalizedRect(
                x=intersection_right,
                y=middle_top,
                width=(
                    source_right
                    - intersection_right
                ),
                height=middle_height,
            )
        )

    return tuple(pieces)


def _is_opaque_photo(
    photo: Photo,
) -> bool:
    """
    JPEG photographs are opaque.

    PNG is deliberately excluded because it may contain alpha.
    """

    return (
        photo.path.suffix.lower()
        in {".jpg", ".jpeg"}
    )


def _rect_is_fully_covered(
    rect: NormalizedRect,
    opaque_rects: list[NormalizedRect],
) -> bool:
    remaining = [rect]

    for cover in opaque_rects:
        next_remaining: list[
            NormalizedRect
        ] = []

        for region in remaining:
            next_remaining.extend(
                _subtract_rect(
                    region,
                    cover,
                )
            )

        remaining = next_remaining

        if not remaining:
            return True

    return False


def visible_cover_scatter_items(
    items: tuple[CoverScatterItem, ...],
) -> tuple[CoverScatterItem, ...]:
    """
    Return only items that contribute visible pixels.

    Items are ordered back-to-front. We inspect them in reverse,
    because later photographs are painted above earlier ones.
    """

    opaque_above: list[
        NormalizedRect
    ] = []

    visible_reversed: list[
        CoverScatterItem
    ] = []

    for item in reversed(items):
        if not _rect_is_fully_covered(
            item.rect,
            opaque_above,
        ):
            visible_reversed.append(
                item
            )

        if _is_opaque_photo(
            item.photo
        ):
            opaque_above.append(
                item.rect
            )

    return tuple(
        reversed(
            visible_reversed
        )
    )
