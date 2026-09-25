from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


from .pagination import PageSide, PlannedPage
from .planning import PlanItemKind
from .settings import (
    PageNumberSettings,
    PageInstance,
    PhotoPageSettings,
)


class ImageFit(str, Enum):
    CONTAIN = "contain"
    COVER = "cover"


class HorizontalAlignment(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


@dataclass(frozen=True)
class NormalizedRect:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (
            self.x,
            self.y,
            self.width,
            self.height,
        )

        if any(value < 0 or value > 1 for value in values):
            raise ValueError(
                "Normalized rectangle values must be "
                "between 0 and 1."
            )

        if self.x + self.width > 1 + 1e-9:
            raise ValueError(
                "Rectangle exceeds page width."
            )

        if self.y + self.height > 1 + 1e-9:
            raise ValueError(
                "Rectangle exceeds page height."
            )


@dataclass(frozen=True)
class PhotoSlotComposition:
    image_rect: NormalizedRect
    caption_rect: NormalizedRect | None
    caption: object
    image_fit: ImageFit = ImageFit.CONTAIN
    required_caption_lines: int = 0
    max_caption_lines: int = 0

    @property
    def caption_overflow(self) -> bool:
        return self.required_caption_lines > self.max_caption_lines


@dataclass(frozen=True)
class PageNumberComposition:
    number: int
    rect: NormalizedRect
    alignment: HorizontalAlignment


@dataclass(frozen=True)
class PageComposition:
    page: PlannedPage
    photo_slots: tuple[PhotoSlotComposition, ...] = ()
    page_number: PageNumberComposition | None = None

    @property
    def used_photo_slots(self) -> int:
        return min(
            len(self.page.photos),
            len(self.photo_slots),
        )

    @property
    def unused_photo_slots(self) -> int:
        return max(
            0,
            len(self.photo_slots) - len(self.page.photos),
        )


def fit_contained_rect(
    box: NormalizedRect,
    *,
    pixel_width: int,
    pixel_height: int,
) -> NormalizedRect:
    if pixel_width <= 0 or pixel_height <= 0:
        return box

    image_ratio = pixel_width / pixel_height
    box_ratio = box.width / box.height

    if image_ratio >= box_ratio:
        width = box.width
        height = width / image_ratio
    else:
        height = box.height
        width = height * image_ratio

    return NormalizedRect(
        x=box.x + (box.width - width) / 2,
        y=box.y + (box.height - height) / 2,
        width=width,
        height=height,
    )


class TemplateLayout(Protocol):
    def compose(
        self,
        page: PlannedPage,
        instance: PageInstance,
        page_numbers: PageNumberSettings,
        *,
        page_width_mm: float = 210.0,
        page_height_mm: float = 297.0,
        reserved_caption_lines: int | None = None,
    ) -> PageComposition:
        ...


class TemplateLayoutRegistry:
    def __init__(self) -> None:
        self._layouts: dict[str, TemplateLayout] = {}

    def register(
        self,
        template_id: str,
        layout: TemplateLayout,
    ) -> None:
        if not template_id:
            raise ValueError(
                "Template ID cannot be empty."
            )

        if template_id in self._layouts:
            raise ValueError(
                "Layout is already registered: "
                f"{template_id}"
            )

        self._layouts[template_id] = layout

    def find(self, template_id: str | None) -> TemplateLayout | None:
        return self._layouts.get(template_id)

    def get(
        self,
        template_id: str,
    ) -> TemplateLayout:
        try:
            return self._layouts[template_id]
        except KeyError:
            raise KeyError(
                f"No layout registered for template: "
                f"{template_id}"
            ) from None


def compose_page_number(
    page: PlannedPage,
    *,
    page_number_height: float = 0.025,
    page_number_width: float = 0.12,
    page_number_y: float = 0.965,
    page_number_outer_margin: float = 0.06,
) -> PageNumberComposition:
    """
    Compose the common album page number.

    Page numbering is independent from the page template.
    """
    if page.side == PageSide.LEFT:
        x = page_number_outer_margin
        alignment = HorizontalAlignment.LEFT
    else:
        x = (
            1
            - page_number_outer_margin
            - page_number_width
        )
        alignment = HorizontalAlignment.RIGHT

    return PageNumberComposition(
        number=page.number,
        rect=NormalizedRect(
            x=x,
            y=page_number_y,
            width=page_number_width,
            height=page_number_height,
        ),
        alignment=alignment,
    )


def create_builtin_layout_registry() -> TemplateLayoutRegistry:
    """Build layouts from all discovered packs."""
    from photoalbum.template_engine.discovery import register_discovered_layouts

    registry = TemplateLayoutRegistry()
    register_discovered_layouts(registry)
    return registry


class PageComposer:
    def __init__(
        self,
        registry: TemplateLayoutRegistry | None = None,
    ) -> None:
        self._registry = (
            registry
            or create_builtin_layout_registry()
        )

    def compose_instance(
        self, instance: PageInstance, photos=(), *, page_width_mm=210.0, page_height_mm=297.0,
    ) -> PageComposition:
        """Compose an occurrence outside pagination using its optional layout."""
        page = PlannedPage(
            number=0, side=PageSide.RIGHT, kind=None, template_id=instance.template_id,
            photos=tuple(photos), page_instance=instance,
        )
        return self.compose(
            page, page_numbers=PageNumberSettings(enabled=False),
            page_width_mm=page_width_mm, page_height_mm=page_height_mm,
        )

    def required_caption_lines(
        self,
        page: PlannedPage,
        photo_settings: PhotoPageSettings | None = None,
        *,
        page_width_mm: float = 210.0,
        page_height_mm: float = 297.0,
    ) -> int:
        """Return the real, unclipped caption requirement.

        This value is deliberately NOT limited by
        layout.max_caption_lines.  Plan diagnostics need the real
        requirement in order to report caption overflow.
        """
        if (
            page.kind != PlanItemKind.PHOTO_GROUP
            or page.photo_capacity <= 0
            or page.template_id is None
        ):
            return 0

        instance = self._page_instance(page, photo_settings)

        layout = self._registry.get(
            page.template_id
        )

        measure = getattr(layout, "required_caption_lines", None)
        if measure is None:
            return 0
        return measure(page, instance, page_width_mm=page_width_mm,
                       page_height_mm=page_height_mm)

    @staticmethod
    def _spread_page_numbers(
        page: PlannedPage,
    ) -> set[int]:
        """Return interior page numbers belonging to the spread.

        Interior layout:
          p1      : alone on the right
          p2 / p3 : facing spread
          p4 / p5 : facing spread
          ...
        """
        if page.number <= 1:
            return {page.number}

        if page.number % 2 == 0:
            return {
                page.number,
                page.number + 1,
            }

        return {
            page.number - 1,
            page.number,
        }

    def spread_required_caption_lines(
        self,
        page: PlannedPage,
        album_pages,
        photo_settings: PhotoPageSettings | None = None,
        *,
        page_width_mm: float = 210.0,
        page_height_mm: float = 297.0,
    ) -> int:
        """Return the real maximum caption need of the spread."""

        spread_numbers = self._spread_page_numbers(
            page
        )

        required_max = 0

        for candidate in album_pages:
            if candidate.number not in spread_numbers:
                continue

            required_max = max(
                required_max,
                self.required_caption_lines(
                    candidate,
                    photo_settings,
                    page_width_mm=page_width_mm,
                    page_height_mm=page_height_mm,
                ),
            )

        return required_max

    def spread_caption_lines(
        self,
        page: PlannedPage,
        album_pages,
        photo_settings: PhotoPageSettings | None = None,
        *,
        page_width_mm: float = 210.0,
        page_height_mm: float = 297.0,
    ) -> int:
        """Return the caption reserve used by this page.

        The real requirement is shared across the whole spread,
        while the final reserve is capped by THIS page template.
        """
        if (
            page.kind != PlanItemKind.PHOTO_GROUP
            or page.template_id is None
        ):
            return 0

        layout = self._registry.get(
            page.template_id
        )

        reserve = getattr(layout, "reserve_caption_lines", None)
        if reserve is None:
            return 0

        required = (
            self.spread_required_caption_lines(
                page,
                album_pages,
                photo_settings,
                page_width_mm=page_width_mm,
                page_height_mm=page_height_mm,
            )
        )

        return reserve(required)

    def compose(
        self,
        page: PlannedPage,
        photo_settings: PhotoPageSettings | None = None,
        page_numbers: PageNumberSettings | None = None,
        *,
        page_width_mm: float = 210.0,
        page_height_mm: float = 297.0,
        reserved_caption_lines: int | None = None,
    ) -> PageComposition:
        page_numbers = (
            page_numbers
            or PageNumberSettings()
        )

        layout = self._registry.find(page.template_id)
        if layout is None and page.photo_capacity > 0:
            # A template with photo slots must supply their layout.
            self._registry.get(page.template_id)
        if layout is None:
            page_number = None

            if page_numbers.enabled:
                page_number = compose_page_number(
                    page
                )

            return PageComposition(
                page=page,
                page_number=page_number,
            )

        return layout.compose(
            page,
            self._page_instance(page, photo_settings),
            page_numbers,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            reserved_caption_lines=reserved_caption_lines,
        )

    @staticmethod
    def _page_instance(page, photo_settings):
        if page.page_instance is not None:
            return page.page_instance
        if photo_settings is not None and photo_settings.template_id == page.template_id:
            return photo_settings.page
        from photoalbum.template_engine.instances import create_template_instance
        return create_template_instance(page.template_id)
