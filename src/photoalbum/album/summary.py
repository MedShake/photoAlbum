from __future__ import annotations

from dataclasses import dataclass, field

from .builder import AlbumBuildResult
from .pagination import BlankPageReason
from .planning import PlanItemKind


@dataclass(frozen=True)
class PeriodFillSuggestion:
    year: int
    month: int
    available_photo_slots: int


@dataclass(frozen=True)
class AlbumPlanSummary:
    photo_count: int
    total_pages: int

    photo_pages: int
    divider_pages: int
    special_pages: int

    technical_blank_pages: int
    editorial_blank_pages: int

    print_compatible: bool
    print_pages_to_add: int
    print_page_multiple: int | None

    period_fill_suggestions: tuple[
        PeriodFillSuggestion,
        ...
    ] = field(default_factory=tuple)


class AlbumSummaryBuilder:
    def build(
        self,
        result: AlbumBuildResult,
    ) -> AlbumPlanSummary:
        pages = result.pagination.pages

        photo_count = sum(
            len(page.photos)
            for page in pages
        )

        photo_pages = sum(
            1
            for page in pages
            if page.kind == PlanItemKind.PHOTO_GROUP
        )

        divider_pages = sum(
            1
            for page in pages
            if page.kind in (
                PlanItemKind.MONTH_DIVIDER,
                PlanItemKind.YEAR_DIVIDER,
            )
        )

        special_pages = sum(
            1
            for page in pages
            if page.kind == PlanItemKind.SPECIAL_PAGE
        )

        technical_blank_pages = sum(
            1
            for page in pages
            if (
                page.blank_reason
                == BlankPageReason.TECHNICAL
            )
        )

        editorial_blank_pages = sum(
            1
            for page in pages
            if (
                page.blank_reason
                == BlankPageReason.EDITORIAL
            )
        )

        suggestions = tuple(
            PeriodFillSuggestion(
                year=period.year,
                month=period.month,
                available_photo_slots=(
                    period.unused_photo_slots
                ),
            )
            for period
            in result.pagination.period_end_capacities
            if period.unused_photo_slots > 0
        )

        # Use the canonical physical document page count.
        # pagination.pages contains interior pages only;
        # AlbumBuildResult also accounts for the four covers.
        total_pages = result.total_page_count

        return AlbumPlanSummary(
            photo_count=photo_count,
            total_pages=total_pages,
            photo_pages=photo_pages,
            divider_pages=divider_pages,
            special_pages=special_pages,
            technical_blank_pages=technical_blank_pages,
            editorial_blank_pages=editorial_blank_pages,
            print_compatible=(
                result.print_diagnostic.compatible
            ),
            print_pages_to_add=(
                result.print_diagnostic.pages_to_add
            ),
            print_page_multiple=(
                result.print_diagnostic.page_multiple
            ),
            period_fill_suggestions=suggestions,
        )

