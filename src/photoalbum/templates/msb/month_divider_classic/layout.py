from __future__ import annotations

from dataclasses import dataclass

from photoalbum.album.composition import NormalizedRect


@dataclass(frozen=True)
class MonthDividerLayout:
    """
    Built-in classic month divider.

    Geometry is normalized so Preview and PDF can share it.
    """

    title_rect: NormalizedRect
    cities_rect: NormalizedRect

    title_font_pt: float = 32.0
    cities_font_pt: float = 14.0

def classic_month_divider_layout(
    *,
    page_width_mm: float,
    page_height_mm: float,
) -> MonthDividerLayout:
    """
    Build the classic month-divider layout for a physical page.

    The historical template uses physical millimetre dimensions.
    They are normalized here so Preview and PDF share exactly
    the same geometry on every supported page format.
    """
    if page_width_mm <= 0 or page_height_mm <= 0:
        raise ValueError(
            "Page dimensions must be positive."
        )

    horizontal_margin_mm = 10.0

    return MonthDividerLayout(
        # PHP: title starts around y=10 mm.
        #
        # The historical x=0.05 / width=0.90 proportions are
        # equivalent to symmetric physical margins on A4, so
        # use the intended 10 mm margins explicitly.
        title_rect=NormalizedRect(
            x=horizontal_margin_mm / page_width_mm,
            y=10.0 / page_height_mm,
            width=(
                page_width_mm
                - 2 * horizontal_margin_mm
            ) / page_width_mm,
            height=20.0 / page_height_mm,
        ),

        # PHP: cities start around y=40 mm and keep a
        # 10 mm physical margin on each side.
        cities_rect=NormalizedRect(
            x=horizontal_margin_mm / page_width_mm,
            y=40.0 / page_height_mm,
            width=(
                page_width_mm
                - 2 * horizontal_margin_mm
            ) / page_width_mm,
            height=0.65,
        ),
    )


def month_cities(page, album_pages):
    """Ordered, unique cities from the photographs printed in this period."""
    sample = getattr(page, "cities", None)
    if sample is not None:
        return tuple(sample)
    from photoalbum.album.planning import PlanItemKind
    cities = []
    for candidate in album_pages:
        if (candidate.kind != PlanItemKind.PHOTO_GROUP
                or candidate.year != page.year or candidate.month != page.month):
            continue
        for photo in candidate.photos:
            city = photo.city.strip() if photo.city else None
            if city and city not in cities:
                cities.append(city)
    return tuple(cities)
