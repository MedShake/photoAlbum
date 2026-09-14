from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from photoalbum.models import Photo

from .planning import AlbumPlan, PlanItem, PlanItemKind
from .settings import (
    AlbumStructureSettings,
    DividerPlacement,
)
from .templates import TemplateRegistry


class PageSide(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class BlankPageReason(str, Enum):
    TECHNICAL = "technical"
    EDITORIAL = "editorial"


@dataclass(frozen=True)
class PlannedPage:
    number: int
    side: PageSide
    kind: PlanItemKind | None
    template_id: str | None

    year: int | None = None
    month: int | None = None

    photos: tuple[Photo, ...] = ()
    photo_capacity: int = 0

    blank_reason: BlankPageReason | None = None

    @property
    def unused_photo_slots(self) -> int:
        return self.photo_capacity - len(self.photos)

    @property
    def is_blank(self) -> bool:
        return self.blank_reason is not None


@dataclass(frozen=True)
class PeriodEndCapacity:
    year: int
    month: int
    unused_photo_slots: int


@dataclass
class PaginationResult:
    pages: list[PlannedPage] = field(
        default_factory=list
    )
    period_end_capacities: list[PeriodEndCapacity] = field(
        default_factory=list
    )


class PaginationEngine:
    def __init__(
        self,
        registry: TemplateRegistry,
    ) -> None:
        self._registry = registry

    def paginate(
        self,
        plan: AlbumPlan,
        settings: AlbumStructureSettings | None = None,
    ) -> PaginationResult:
        result = PaginationResult()

        for item in plan.items:
            if item.kind == PlanItemKind.PHOTO_GROUP:
                self._append_photo_pages(
                    result,
                    item,
                )
                continue

            if item.kind in (
                PlanItemKind.MONTH_DIVIDER,
                PlanItemKind.YEAR_DIVIDER,
            ):
                self._append_divider_page(
                    result,
                    item,
                    settings,
                )
                continue

            self._record_previous_month_capacity(
                result
            )

            self._append_single_page(
                result,
                item,
            )
            
        self._record_previous_month_capacity(
            result
        )    
        return result

    def _append_photo_pages(
        self,
        result: PaginationResult,
        item: PlanItem,
    ) -> None:
        template = self._registry.get(
            item.template_id
        )
        capacity = template.photo_capacity

        for start in range(
            0,
            len(item.photos),
            capacity,
        ):
            photos = item.photos[
                start:start + capacity
            ]

            result.pages.append(
                PlannedPage(
                    number=len(result.pages) + 1,
                    side=self._side_for_next_page(
                        result
                    ),
                    kind=item.kind,
                    template_id=item.template_id,
                    year=item.year,
                    month=item.month,
                    photos=photos,
                    photo_capacity=capacity,
                )
            )

    def _append_divider_page(
        self,
        result: PaginationResult,
        item: PlanItem,
        settings: AlbumStructureSettings | None,
    ) -> None:
        placement = self._divider_placement(
            item,
            settings,
        )

        if placement == DividerPlacement.RIGHT_PAGE:
            if (
                self._side_for_next_page(result)
                == PageSide.LEFT
            ):
                self._append_technical_blank(result)

        elif (
            placement
            == DividerPlacement.RIGHT_PAGE_WITH_BLANK_FACING
        ):
            self._prepare_blank_facing_page(result)

        if item.kind in (
            PlanItemKind.MONTH_DIVIDER,
            PlanItemKind.YEAR_DIVIDER,
        ):
            self._record_previous_month_capacity(
                result
            )

        self._append_single_page(
            result,
            item,
        )

    def _append_technical_blank(
        self,
        result: PaginationResult,
    ) -> None:
        template_id = None
        capacity = 0
        year = None
        month = None

        for page in reversed(result.pages):
            if page.kind == PlanItemKind.PHOTO_GROUP:
                template_id = page.template_id
                capacity = page.photo_capacity
                year = page.year
                month = page.month
                break

            if not page.is_blank:
                break

        result.pages.append(
            PlannedPage(
                number=len(result.pages) + 1,
                side=self._side_for_next_page(
                    result
                ),
                kind=None,
                template_id=template_id,
                year=year,
                month=month,
                photo_capacity=capacity,
                blank_reason=BlankPageReason.TECHNICAL,
            )
        )

    def _prepare_blank_facing_page(
        self,
        result: PaginationResult,
    ) -> None:
        if not result.pages:
            return

        if (
            self._side_for_next_page(result)
            == PageSide.RIGHT
        ):
            self._append_technical_blank(result)

        self._append_editorial_blank(result)

    def _append_editorial_blank(
        self,
        result: PaginationResult,
    ) -> None:
        year: int | None = None
        month: int | None = None

        for page in reversed(result.pages):
            if page.year is not None:
                year = page.year

            if page.month is not None:
                month = page.month

            if year is not None or month is not None:
                break

        result.pages.append(
            PlannedPage(
                number=len(result.pages) + 1,
                side=self._side_for_next_page(
                    result
                ),
                kind=None,
                template_id=None,
                year=year,
                month=month,
                photo_capacity=0,
                blank_reason=BlankPageReason.EDITORIAL,
            )
        )

    def _record_previous_month_capacity(
        self,
        result: PaginationResult,
    ) -> None:
        year: int | None = None
        month: int | None = None
        unused_slots = 0

        for page in reversed(result.pages):
            if (
                page.blank_reason
                == BlankPageReason.EDITORIAL
            ):
                continue

            if (
                page.blank_reason
                == BlankPageReason.TECHNICAL
            ):
                unused_slots += page.photo_capacity

                if year is None:
                    year = page.year
                    month = page.month

                continue

            if page.kind != PlanItemKind.PHOTO_GROUP:
                break

            if year is None:
                year = page.year
                month = page.month

            if (
                page.year != year
                or page.month != month
            ):
                break

            unused_slots += page.unused_photo_slots

        if year is None or month is None:
            return

        result.period_end_capacities.append(
            PeriodEndCapacity(
                year=year,
                month=month,
                unused_photo_slots=unused_slots,
            )
        )

    def _append_single_page(
        self,
        result: PaginationResult,
        item: PlanItem,
    ) -> None:
        result.pages.append(
            PlannedPage(
                number=len(result.pages) + 1,
                side=self._side_for_next_page(
                    result
                ),
                kind=item.kind,
                template_id=item.template_id,
                year=item.year,
                month=item.month,
            )
        )

    @staticmethod
    def _divider_placement(
        item: PlanItem,
        settings: AlbumStructureSettings | None,
    ) -> DividerPlacement:
        if settings is None:
            return DividerPlacement.NATURAL

        if item.kind == PlanItemKind.MONTH_DIVIDER:
            return settings.month_dividers.placement

        if item.kind == PlanItemKind.YEAR_DIVIDER:
            return settings.year_dividers.placement

        return DividerPlacement.NATURAL

    @staticmethod
    def _side_for_next_page(
        result: PaginationResult,
    ) -> PageSide:
        number = len(result.pages) + 1

        return (
            PageSide.RIGHT
            if number % 2 == 1
            else PageSide.LEFT
        )