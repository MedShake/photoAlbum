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
class CoverScatterSettings:
    # 0 means: use every eligible dated photo.
    photo_count: int = 0

    # All proposals remain reproducible.
    seeds: tuple[int, ...] = (0,)
    selected_seed_index: int = 0

    @property
    def seed(self) -> int:
        if not self.seeds:
            return 0

        index = min(
            max(self.selected_seed_index, 0),
            len(self.seeds) - 1,
        )

        return self.seeds[index]


@dataclass(frozen=True)
class CoverSettings:
    position: CoverPosition
    template_id: str
    scatter: CoverScatterSettings = field(
        default_factory=CoverScatterSettings
    )


@dataclass(frozen=True)
class DividerSettings:
    enabled: bool
    template_id: str
    placement: DividerPlacement = DividerPlacement.RIGHT_PAGE


@dataclass(frozen=True)
class PhotoCaptionSettings:
    show_datetime: bool = True
    show_location: bool = True


@dataclass(frozen=True)
class PhotoPageSettings:
    template_id: str
    caption: PhotoCaptionSettings = field(
        default_factory=PhotoCaptionSettings
    )


@dataclass(frozen=True)
class PageNumberSettings:
    enabled: bool = True


@dataclass(frozen=True)
class PrintSettings:
    # None means no page-count constraint.
    page_multiple: int | None = None


@dataclass(frozen=True)
class SpecialPage:
    template_id: str


@dataclass
class AlbumStructureSettings:
    covers: dict[CoverPosition, CoverSettings]

    month_dividers: DividerSettings
    year_dividers: DividerSettings

    photo_pages: PhotoPageSettings

    page_numbers: PageNumberSettings = field(
        default_factory=PageNumberSettings
    )

    print_settings: PrintSettings = field(
        default_factory=PrintSettings
    )

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