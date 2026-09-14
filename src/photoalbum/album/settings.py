from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import CoverPosition


class DividerPlacement(str, Enum):
    NATURAL = "natural"
    RIGHT_PAGE = "right_page"
    RIGHT_PAGE_WITH_BLANK_FACING = (
        "right_page_with_blank_facing"
    )


@dataclass(frozen=True)
class CoverSettings:
    position: CoverPosition
    template_id: str


@dataclass(frozen=True)
class DividerSettings:
    enabled: bool
    template_id: str
    placement: DividerPlacement = DividerPlacement.RIGHT_PAGE


@dataclass(frozen=True)
class PhotoPageSettings:
    template_id: str


@dataclass(frozen=True)
class SpecialPage:
    template_id: str


@dataclass
class AlbumStructureSettings:
    covers: dict[CoverPosition, CoverSettings]

    month_dividers: DividerSettings
    year_dividers: DividerSettings

    photo_pages: PhotoPageSettings

    front_matter: list[SpecialPage] = field(
        default_factory=list
    )
    back_matter: list[SpecialPage] = field(
        default_factory=list
    )

    def year_dividers_available(
        self,
        years: set[int],
    ) -> bool:
        return len(years) > 1

    def should_use_year_dividers(
        self,
        years: set[int],
    ) -> bool:
        return (
            self.year_dividers.enabled
            and self.year_dividers_available(years)
        )