from __future__ import annotations

from dataclasses import dataclass

from .composition import NormalizedRect


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

    def color_for_month(
        self,
        month: int,
    ) -> tuple[int, int, int]:
        return MONTH_COLORS.get(
            month,
            (0, 0, 0),
        )


MONTH_COLORS: dict[int, tuple[int, int, int]] = {
    1: (72, 155, 207),
    2: (134, 96, 188),
    3: (76, 168, 108),
    4: (144, 198, 101),
    5: (238, 201, 88),
    6: (242, 162, 91),
    7: (228, 104, 71),
    8: (200, 76, 76),
    9: (210, 108, 162),
    10: (186, 94, 186),
    11: (90, 125, 206),
    12: (88, 185, 174),
}


CLASSIC_MONTH_DIVIDER_LAYOUT = MonthDividerLayout(
    # PHP: title starts around y=10 mm and spans the page width.
    title_rect=NormalizedRect(
        x=0.05,
        y=10.0 / 297.0,
        width=0.90,
        height=20.0 / 297.0,
    ),

    # PHP: cities start around y=40 mm.
    cities_rect=NormalizedRect(
        x=10.0 / 210.0,
        y=40.0 / 297.0,
        width=190.0 / 210.0,
        height=0.65,
    ),
)
