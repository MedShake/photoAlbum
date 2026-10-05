from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from photoalbum.models import Photo

from .planning import AlbumPlan, PlanItem, PlanItemKind
from .settings import (
    AlbumStructureSettings,
    DividerPlacement,
    PageInstance,
    ContentAnchor,
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
    day: int | None = None

    photos: tuple[Photo, ...] = ()
    photo_capacity: int = 0

    # Original configurable occurrence when this page comes
    # from a PageInstance.
    page_instance: PageInstance | None = None

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
        self._overrides = {item.photo_identity: item.page for item in settings.photo_page_overrides} if settings else {}
        self._insertions = {}
        if settings:
            geometry = settings.effective_page_format()
            for insertion in settings.body_insertions:
                if insertion.enabled and self._registry.get(insertion.page.template_id).is_compatible_with_page(
                    geometry.width_mm, geometry.height_mm
                ):
                    self._insertions.setdefault(insertion.anchor, []).append(insertion.page)

        for item in plan.items:
            if item.kind == PlanItemKind.PHOTO_GROUP:
                self._append_photo_pages(
                    result,
                    item,
                )
                continue

            if item.kind in (
                PlanItemKind.DAY_DIVIDER,
                PlanItemKind.MONTH_DIVIDER,
                PlanItemKind.YEAR_DIVIDER,
            ):
                self._append_divider_page(
                    result,
                    item,
                    settings,
                )
                self._append_insertions(result, ContentAnchor(
                    item.kind.value, year=item.year, month=item.month, day=item.day), item)
                continue

            self._append_single_page(
                result,
                item,
            )
            
        self._record_period_capacities(result)

        return result

    def _append_photo_pages(
        self,
        result: PaginationResult,
        item: PlanItem,
    ) -> None:
        start = 0
        while start < len(item.photos):
            instance = self._overrides.get(item.photos[start].identity, item.page_instance)
            template_id = instance.template_id if instance else item.template_id
            capacity = self._registry.get(template_id).photo_capacity
            stop = min(start + capacity, len(item.photos))
            for index in range(start, stop):
                if index > start and item.photos[index].identity in self._overrides:
                    stop = index
                    break
                if ContentAnchor("photo", photo_identity=item.photos[index].identity) in self._insertions:
                    stop = index + 1
                    break
            photos = item.photos[
                start:stop
            ]

            result.pages.append(
                PlannedPage(
                    number=len(result.pages) + 1,
                    side=self._side_for_next_page(
                        result
                    ),
                    kind=item.kind,
                    template_id=template_id,
                    year=item.year,
                    month=item.month,
                    day=item.day,
                    photos=photos,
                    photo_capacity=capacity,
                    page_instance=instance,
                )
            )
            self._append_insertions(result, ContentAnchor("photo", photo_identity=photos[-1].identity), item,
                                    photo=photos[-1])
            start = stop

    def _append_insertions(self, result, anchor, item, photo=None) -> None:
        date = photo.capture_datetime if photo is not None else None
        for instance in self._insertions.get(anchor, ()):
            self._append_single_page(result, PlanItem(
                kind=PlanItemKind.BODY_SPECIAL_PAGE, template_id=instance.template_id,
                page_instance=instance,
                year=date.year if date else item.year,
                month=date.month if date else item.month,
                day=date.day if date else item.day,
            ))

    def _record_period_capacities(self, result: PaginationResult) -> None:
        # Periods are semantic, not delimited by arbitrary non-photo pages.
        periods = {}
        for index, page in enumerate(result.pages):
            if page.kind == PlanItemKind.PHOTO_GROUP:
                periods[(page.year, page.month)] = index
        for (year, month), last in periods.items():
            if year is None or month is None:
                continue
            unused = result.pages[last].unused_photo_slots
            last_photo = result.pages[last].photos[-1]
            if ContentAnchor("photo", photo_identity=last_photo.identity) in self._insertions:
                # New photos must follow this insertion, so the forced end's
                # spare slots cannot absorb additional chronological content.
                unused = 0
            # Only terminal spare capacity is reusable across a month boundary.
            # Earlier forced cuts (day, override, insertion) are intentional.
            for page in result.pages[last + 1:]:
                if page.kind in (PlanItemKind.MONTH_DIVIDER, PlanItemKind.YEAR_DIVIDER):
                    break
                if page.kind == PlanItemKind.PHOTO_GROUP:
                    break
                if (page.blank_reason == BlankPageReason.TECHNICAL
                        and (page.year, page.month) == (year, month)):
                    unused += page.photo_capacity
            result.period_end_capacities.append(PeriodEndCapacity(year, month, unused))

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
                day=item.day,
                page_instance=item.page_instance,
            )
        )

    @staticmethod
    def _divider_placement(
        item: PlanItem,
        settings: AlbumStructureSettings | None,
    ) -> DividerPlacement:
        if settings is None:
            return DividerPlacement.NATURAL

        if item.kind == PlanItemKind.DAY_DIVIDER:
            return settings.day_dividers.placement

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
