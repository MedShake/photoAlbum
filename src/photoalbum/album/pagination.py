from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from importlib import import_module

from photoalbum.models import Photo

from .planning import AlbumPlan, PlanItem, PlanItemKind
from .settings import (
    AlbumStructureSettings,
    DividerPlacement,
    PageInstance,
    ContentAnchor,
)
from .templates import AutomaticPhotoPageContext, TemplateKind, TemplateRegistry


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
        *,
        forced_photo_page_starts: set[str] | None = None,
    ) -> PaginationResult:
        result = PaginationResult()
        self._page_geometry = settings.effective_page_format() if settings else None
        self._overrides = {item.photo_identity: item.page for item in settings.photo_page_overrides} if settings else {}
        self._override_boundaries = set(self._overrides) | set(forced_photo_page_starts or ())
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
            override_instance = self._overrides.get(item.photos[start].identity)
            maximum_capacity = self._maximum_photo_page_capacity(
                item, override_instance
            )
            boundary_stop = min(start + maximum_capacity, len(item.photos))
            for index in range(start, boundary_stop):
                if index > start and item.photos[index].identity in self._override_boundaries:
                    boundary_stop = index
                    break
                anchor = ContentAnchor(
                    "photo", photo_identity=item.photos[index].identity
                )
                if anchor in self._insertions:
                    boundary_stop = index + 1
                    break

            admissible = item.photos[start:boundary_stop]
            instance = override_instance
            if instance is None:
                instance = self._resolve_default_photo_page(item, admissible)
            template_id = instance.template_id
            capacity = self._registry.get(template_id).photo_capacity
            stop = min(start + capacity, boundary_stop)
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

    def _maximum_photo_page_capacity(
        self,
        item: PlanItem,
        override: PageInstance | None,
    ) -> int:
        if override is not None:
            return self._registry.get(override.template_id).photo_capacity
        if item.automatic_photo_page_mode is not None:
            definition = self._registry.get_automatic_photo_page_mode(
                item.automatic_photo_page_mode.mode_id
            )
            return max(
                self._registry.get(template_id).photo_capacity
                for template_id in definition.template_ids
            )
        instance = item.page_instance
        template_id = instance.template_id if instance is not None else item.template_id
        if template_id is None:
            raise ValueError("Photo group has no fixed template or automatic mode.")
        return self._registry.get(template_id).photo_capacity

    def _resolve_default_photo_page(
        self,
        item: PlanItem,
        admissible_photos: tuple[Photo, ...],
    ) -> PageInstance:
        if item.automatic_photo_page_mode is None:
            if item.page_instance is not None:
                return item.page_instance
            if item.template_id is None:
                raise ValueError("Photo group has no fixed template or automatic mode.")
            return PageInstance(template_id=item.template_id)

        if self._page_geometry is None:
            raise ValueError("Automatic photo-page modes require album page geometry.")
        selection = item.automatic_photo_page_mode
        definition = self._registry.get_automatic_photo_page_mode(selection.mode_id)
        selector = None
        if definition.selector_reference is not None:
            module_name, attribute = definition.selector_reference.split(":", 1)
            selector = getattr(import_module(module_name), attribute, None)
        if not callable(selector):
            raise ValueError(
                f"Automatic mode {selection.mode_id!r} has no callable selector."
            )
        template_id = selector(AutomaticPhotoPageContext(
            photos=tuple(admissible_photos),
            page_width_mm=self._page_geometry.width_mm,
            page_height_mm=self._page_geometry.height_mm,
        ))
        if template_id not in definition.template_ids:
            raise ValueError(
                f"Automatic mode {selection.mode_id!r} returned undeclared template "
                f"{template_id!r}."
            )
        template = self._registry.get(template_id)
        if (
            not template.supports(TemplateKind.PHOTO_PAGE)
            or template.pack_id != definition.pack_id
        ):
            raise ValueError(
                f"Automatic mode {selection.mode_id!r} returned an invalid template."
            )
        if not template.is_compatible_with_page(
            self._page_geometry.width_mm, self._page_geometry.height_mm
        ):
            raise ValueError(
                f"Automatic mode {selection.mode_id!r} returned an incompatible template."
            )
        return PageInstance(
            template_id=template_id,
            instance_id=selection.instance_id,
            settings=dict(selection.settings),
        )

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
