from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import random
from math import isclose
from secrets import randbelow
from typing import Callable, Iterable

from photoalbum.models import Photo, displayed_photo_dimensions

from photoalbum.album.composition import NormalizedRect


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
    photo: Photo | None
    rect: NormalizedRect


@dataclass(frozen=True)
class CoverScatterComposition:
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
    return displayed_photo_dimensions(photo) or (4, 3)


def _photo_rect(
    rng: random.Random,
    photo: Photo,
    *,
    page_width_mm: float,
    page_height_mm: float,
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

    # Historical physical values expressed in millimetres.
    # Normalize them against the actual page format.
    margin_x = 8.0 / page_width_mm
    margin_y = 8.0 / page_height_mm

    if ratio >= 1.0:
        # Determine the physical dimensions first, then
        # normalize each axis against its own page dimension.
        width_mm = 32.0
        height_mm = width_mm / ratio

        width = width_mm / page_width_mm
        height = height_mm / page_height_mm
    else:
        height_mm = 42.0
        width_mm = height_mm * ratio

        width = width_mm / page_width_mm
        height = height_mm / page_height_mm

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
    month_name: Callable[[int], str],
    page_width_mm: float = 210.0,
    page_height_mm: float = 297.0,
) -> CoverScatterComposition:
    """
    Build the historical random stacked-photo cover.

    The classic built-in template deliberately uses all dated
    photos from the project.
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
                page_width_mm=page_width_mm,
                page_height_mm=page_height_mm,
            ),
        )
        for photo in shuffled
    )

    return CoverScatterComposition(
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
        photo is not None
        and photo.filename.lower().endswith((".jpg", ".jpeg"))
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


# Frozen geometry is specific to the physical page dimensions. Portrait and
# landscape (or two different paper formats) must never share a proposal.
def proposal_matches_dimensions(
    snapshot: dict, page_width_mm: float, page_height_mm: float,
) -> bool:
    dimensions = snapshot.get("page_dimensions_mm")
    if not isinstance(dimensions, (list, tuple)) or len(dimensions) != 2:
        return False
    try:
        return (
            isclose(float(dimensions[0]), page_width_mm, abs_tol=1e-6)
            and isclose(float(dimensions[1]), page_height_mm, abs_tol=1e-6)
        )
    except (TypeError, ValueError):
        return False


def freeze_cover_scatter(
    composition: CoverScatterComposition, *,
    page_width_mm: float = 210.0, page_height_mm: float = 297.0,
) -> dict:
    """Persist the visible geometry and the physical page it belongs to."""
    return {
        "title": composition.title,
        "page_dimensions_mm": [float(page_width_mm), float(page_height_mm)],
        "items": [
            {"photo_id": item.photo.identity, "rect": [
                item.rect.x, item.rect.y, item.rect.width, item.rect.height,
            ]}
            for item in visible_cover_scatter_items(composition.items)
        ],
    }


def thaw_cover_scatter(snapshot: dict, photos: Iterable[Photo]) -> CoverScatterComposition:
    known = {photo.identity: photo for photo in photos}
    items = []
    for record in snapshot["items"]:
        values = record["rect"]
        rect = NormalizedRect(*map(float, values))
        items.append(CoverScatterItem(known.get(record["photo_id"]), rect))
    return CoverScatterComposition(str(snapshot["title"]), tuple(items))


def scatter_dimensions_key(page_width_mm: float, page_height_mm: float) -> str:
    """Stable, orientation-sensitive identifier for a physical page format."""
    return f"{page_width_mm:.6f}x{page_height_mm:.6f}"


def reset_frozen_scatter_for_dimensions(
    instance, photos: Iterable[Photo], *,
    month_name: Callable[[int], str],
    page_width_mm: float, page_height_mm: float,
):
    """Switch to the proposals already made for this page format, if any.

    A single PageInstance owns all of its format histories; nothing is shared
    with another scatter page. A new format gets its first proposal only when
    selected, never speculatively. Old seed-only pages remain compatible.
    """
    if instance.template_id != "year-photo-scatter":
        return instance
    scatter = instance.settings.get("scatter", {})
    if not isinstance(scatter, dict):
        return instance
    proposals = scatter.get("proposals")
    if not isinstance(proposals, list) or not proposals:
        return instance
    if all(
        isinstance(proposal, dict) and proposal_matches_dimensions(
            proposal, page_width_mm, page_height_mm,
        ) for proposal in proposals
    ):
        return instance

    histories = scatter.get("format_histories")
    histories = dict(histories) if isinstance(histories, dict) else {}

    # Save the departing format in the *same* page instance. Never store an
    # incomplete or mixed-format proposal set as a reusable history.
    first = proposals[0]
    old_dimensions = first.get("page_dimensions_mm") if isinstance(first, dict) else None
    if isinstance(old_dimensions, (tuple, list)) and len(old_dimensions) == 2:
        try:
            old_width, old_height = map(float, old_dimensions)
            if all(
                isinstance(proposal, dict) and proposal_matches_dimensions(
                    proposal, old_width, old_height,
                ) for proposal in proposals
            ):
                histories[scatter_dimensions_key(old_width, old_height)] = {
                    "seeds": list(scatter.get("seeds", [0])),
                    "proposals": list(proposals),
                    "selected_seed_index": int(scatter.get("selected_seed_index", 0)),
                }
        except (TypeError, ValueError, OverflowError):
            pass

    target_key = scatter_dimensions_key(page_width_mm, page_height_mm)
    saved = histories.get(target_key)
    if isinstance(saved, dict):
        saved_seeds = saved.get("seeds")
        saved_proposals = saved.get("proposals")
        if (
            isinstance(saved_seeds, list)
            and isinstance(saved_proposals, list)
            and bool(saved_proposals)
            and len(saved_seeds) == len(saved_proposals)
            and len(saved_seeds) <= 20
            and all(
                isinstance(proposal, dict) and proposal_matches_dimensions(
                    proposal, page_width_mm, page_height_mm,
                ) for proposal in saved_proposals
            )
        ):
            try:
                selection = int(saved.get("selected_seed_index", 0))
            except (TypeError, ValueError, OverflowError):
                selection = 0
            selection = min(max(selection, 0), len(saved_seeds) - 1)
            new_scatter = {
                **scatter, "format_histories": histories,
                "seeds": list(saved_seeds), "proposals": list(saved_proposals),
                "selected_seed_index": selection,
            }
            return replace(instance, settings={**instance.settings, "scatter": new_scatter})

    seed = randbelow(2_147_483_647)
    composition = compose_cover_scatter(
        photos, seed=seed, month_name=month_name,
        page_width_mm=page_width_mm, page_height_mm=page_height_mm,
    )
    frozen = freeze_cover_scatter(
        composition, page_width_mm=page_width_mm, page_height_mm=page_height_mm,
    )
    histories[target_key] = {
        "seeds": [seed], "selected_seed_index": 0, "proposals": [frozen],
    }
    new_scatter = {
        **scatter, "format_histories": histories,
        "seeds": [seed], "selected_seed_index": 0, "proposals": [frozen],
    }
    return replace(instance, settings={**instance.settings, "scatter": new_scatter})


def stored_cover_scatter(instance, photos, *, month_name, page_width_mm, page_height_mm):
    """Use a proposal only for its original page size; never stretch it.

    When loading an older unsized proposal without visiting its settings,
    keep the original seed fallback instead of painting mismatched rectangles.
    """
    scatter = instance.settings.get("scatter", {})
    if not isinstance(scatter, dict):
        scatter = {}
    seeds = scatter.get("seeds", [0]) or [0]
    index = max(0, min(int(scatter.get("selected_seed_index", 0)), len(seeds) - 1))
    proposals = scatter.get("proposals")
    if isinstance(proposals, list) and index < len(proposals):
        snapshot = proposals[index]
        if (
            isinstance(snapshot, dict)
            and isinstance(snapshot.get("items"), list)
            and proposal_matches_dimensions(snapshot, page_width_mm, page_height_mm)
        ):
            return thaw_cover_scatter(snapshot, photos)
    return compose_cover_scatter(
        photos, seed=int(seeds[index]), month_name=month_name,
        page_width_mm=page_width_mm, page_height_mm=page_height_mm,
    )
