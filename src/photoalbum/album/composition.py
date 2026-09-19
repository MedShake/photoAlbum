from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from photoalbum.geocoding.location_caption_builder import LocationCaptionBuilder
from photoalbum.models import Photo

from .pagination import PageSide, PlannedPage
from .planning import PlanItemKind
from .settings import (
    PageNumberSettings,
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
class PhotoCaptionContent:
    capture_datetime: datetime | None = None
    location_text: str | None = None
    caption_text: str | None = None

    @property
    def line_count(self) -> int:
        # Caption and date share the first display line.
        first_line = (
            self.capture_datetime is not None
            or bool(self.caption_text)
        )

        return (
            int(first_line)
            + int(bool(self.location_text))
        )

    @property
    def is_empty(self) -> bool:
        return self.line_count == 0


@dataclass(frozen=True)
class PhotoSlotComposition:
    image_rect: NormalizedRect
    caption_rect: NormalizedRect | None
    caption: PhotoCaptionContent
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


def photo_location_text(
    photo: Photo,
) -> str | None:
    """
    Return the effective editorial location used in the album.

    An explicit editorial choice always wins, including an
    explicitly empty location. Otherwise use the same automatic
    location composition as the Places editor.
    """

    if photo.location_selection_edited:
        if photo.location_text:
            text = photo.location_text.strip()

            if text:
                return text

        return None

    result = LocationCaptionBuilder().build(
        photo.raw_location_data
    )

    return result.caption or None


def build_photo_caption(
    photo: Photo,
    settings: PhotoPageSettings,
) -> PhotoCaptionContent:
    capture_datetime = None
    location_text = None

    if settings.caption.show_datetime:
        capture_datetime = photo.capture_datetime

    if settings.caption.show_location:
        location_text = photo_location_text(photo)

    caption_text = (
        photo.caption.strip()
        if photo.caption and photo.caption.strip()
        else None
    )

    return PhotoCaptionContent(
        capture_datetime=capture_datetime,
        location_text=location_text,
        caption_text=caption_text,
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
        photo_settings: PhotoPageSettings,
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


@dataclass(frozen=True)
class PhotoTemplateLayout:
    cells_factory: Callable[
        [float, float],
        tuple[NormalizedRect, ...],
    ]
    # Classic built-in layout, inspired by the historical
    # PHP renderer:
    #
    # - about 2 mm between image and caption
    # - about 4 mm per caption line
    #
    # Values are normalized against an A4 portrait page height.
    # Other template developers are free to use different values.
    caption_line_height: float = 4.0 / 297.0
    image_caption_gap: float = 2.0 / 297.0
    # Maximum caption height this template is willing to reserve.
    # The renderer may discover that wrapped text needs more lines;
    # that is reported as a diagnostic instead of shrinking photos.
    max_caption_lines: int = 3
    caption_line_counter: (
        Callable[[PhotoCaptionContent, dict, float], int] | None
    ) = None
    caption_line_height_counter: (
        Callable[[dict], float] | None
    ) = None
    image_fit: ImageFit = ImageFit.CONTAIN

    page_number_height: float = 0.025
    page_number_width: float = 0.12
    page_number_y: float = 0.965
    page_number_outer_margin: float = 0.06


    def compose(
        self,
        page: PlannedPage,
        photo_settings: PhotoPageSettings,
        page_numbers: PageNumberSettings,
        *,
        page_width_mm: float = 210.0,
        page_height_mm: float = 297.0,
        reserved_caption_lines: int | None = None,
    ) -> PageComposition:
        cells = self.cells_factory(
            page_width_mm,
            page_height_mm,
        )

        page_number = (
            self._page_number(page)
            if page_numbers.enabled
            else None
        )

        captions = tuple(
            build_photo_caption(
                photo,
                photo_settings,
            )
            for photo in page.photos
        )

        required_caption_lines = tuple(
            self._required_caption_lines(
                caption,
                cell,
                settings=photo_settings.page.settings,
                page_width_mm=page_width_mm,
            )
            for caption, cell in zip(captions, cells)
        )

        if reserved_caption_lines is None:
            row_caption_lines = self._row_caption_lines(
                captions,
                cells,
                settings=photo_settings.page.settings,
                page_width_mm=page_width_mm,
            )
        else:
            reserved = max(
                0,
                min(
                    int(reserved_caption_lines),
                    self.max_caption_lines,
                ),
            )
            row_caption_lines = {
                self._row_key(cell): reserved
                for cell in cells
            }

        slots = tuple(
            self._compose_slot(
                cell=cell,
                caption=(
                    captions[index]
                    if index < len(captions)
                    else PhotoCaptionContent()
                ),
                reserved_lines=row_caption_lines[
                    self._row_key(cell)
                ],
                required_lines=(
                    required_caption_lines[index]
                    if index < len(required_caption_lines)
                    else 0
                ),
                page_height_mm=page_height_mm,
                settings=photo_settings.page.settings,
            )
            for index, cell in enumerate(cells)
        )

        return PageComposition(
            page=page,
            photo_slots=slots,
            page_number=page_number,
        )

    def _required_caption_lines(
        self,
        caption: PhotoCaptionContent,
        cell: NormalizedRect,
        *,
        settings: dict | None = None,
        page_width_mm: float = 210.0,
    ) -> int:
        required = caption.line_count
        if self.caption_line_counter is not None:
            required = self.caption_line_counter(
                caption, settings or {}, cell.width * page_width_mm
            )
        return max(0, int(required))

    def _row_caption_lines(
        self,
        captions: tuple[PhotoCaptionContent, ...],
        cells: tuple[NormalizedRect, ...],
        *,
        settings: dict | None = None,
        page_width_mm: float = 210.0,
    ) -> dict[float, int]:
        result: dict[float, int] = {}

        for index, cell in enumerate(cells):
            key = self._row_key(cell)

            required = 0
            if index < len(captions):
                required = self._required_caption_lines(
                    captions[index],
                    cell,
                    settings=settings,
                    page_width_mm=page_width_mm,
                )

            result[key] = max(
                result.get(key, 0),
                min(required, self.max_caption_lines),
            )

        return result

    @staticmethod
    def _row_key(
        cell: NormalizedRect,
    ) -> float:
        return round(cell.y, 6)

    def _row_has_caption(
        self,
        *,
        row_key: float,
        row_caption_lines: dict[float, int],
    ) -> bool:
        """Return whether a row reserves caption space.

        A row with no visible caption gives the complete cell
        height back to its images.  As soon as one caption is
        visible, the complete caption capacity declared by the
        template is reserved for every cell in that row.
        """
        return row_caption_lines.get(row_key, 0) > 0

    def _compose_slot(
        self,
        *,
        cell: NormalizedRect,
        caption: PhotoCaptionContent,
        reserved_lines: int,
        page_height_mm: float,
        required_lines: int | None = None,
        settings: dict | None = None,
    ) -> PhotoSlotComposition:
        if required_lines is None:
            required_lines = self._required_caption_lines(
                caption,
                cell,
                settings=settings,
            )

        if reserved_lines <= 0:
            return PhotoSlotComposition(
                image_rect=cell,
                caption_rect=None,
                caption=caption,
                image_fit=self.image_fit,
                required_caption_lines=required_lines,
                max_caption_lines=self.max_caption_lines,
            )

        # Layout geometry belongs to the template.  Values are stored
        # normalized against A4 portrait and scaled to the actual page.
        a4_height_mm = 297.0
        if self.caption_line_height_counter is None:
            line_height_mm = (
                self.caption_line_height
                * a4_height_mm
            )
        else:
            line_height_mm = (
                self.caption_line_height_counter(
                    settings or {}
                )
            )

        caption_height = (
            line_height_mm
            * reserved_lines
            / page_height_mm
        )

        image_caption_gap = (
            self.image_caption_gap
            * a4_height_mm
            / page_height_mm
        )

        image_height = (
            cell.height
            - caption_height
            - image_caption_gap
        )

        if image_height <= 0:
            raise ValueError(
                "Photo layout leaves no room for the image."
            )

        image_rect = NormalizedRect(
            x=cell.x,
            y=cell.y,
            width=cell.width,
            height=image_height,
        )

        caption_rect = NormalizedRect(
            x=cell.x,
            y=(
                cell.y
                + image_height
                + image_caption_gap
            ),
            width=cell.width,
            height=caption_height,
        )

        return PhotoSlotComposition(
            image_rect=image_rect,
            caption_rect=caption_rect,
            caption=caption,
            image_fit=self.image_fit,
            required_caption_lines=required_lines,
            max_caption_lines=self.max_caption_lines,
        )

    def _page_number(
        self,
        page: PlannedPage,
    ) -> PageNumberComposition:
        return compose_page_number(
            page,
            page_number_height=self.page_number_height,
            page_number_width=self.page_number_width,
            page_number_y=self.page_number_y,
            page_number_outer_margin=(
                self.page_number_outer_margin
            ),
        )


def create_builtin_layout_registry() -> TemplateLayoutRegistry:
    """Build layouts from all installed packs (MSB remains the default)."""
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

        effective_settings = (
            photo_settings
            or PhotoPageSettings(
                template_id=page.template_id
            )
        )

        layout = self._registry.get(
            page.template_id
        )

        if not isinstance(
            layout,
            PhotoTemplateLayout,
        ):
            return 0

        cells = layout.cells_factory(
            page_width_mm,
            page_height_mm,
        )

        required_max = 0

        for index, photo in enumerate(
            page.photos
        ):
            if index >= len(cells):
                break

            caption = build_photo_caption(
                photo,
                effective_settings,
            )

            required = layout._required_caption_lines(
                caption,
                cells[index],
                settings=effective_settings.page.settings,
                page_width_mm=page_width_mm,
            )

            required_max = max(
                required_max,
                required,
            )

        return required_max

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

        if not isinstance(
            layout,
            PhotoTemplateLayout,
        ):
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

        return min(
            required,
            layout.max_caption_lines,
        )

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

        if (
            page.kind != PlanItemKind.PHOTO_GROUP
            or page.photo_capacity <= 0
            or page.template_id is None
        ):
            page_number = None

            if page_numbers.enabled:
                page_number = compose_page_number(
                    page
                )

            return PageComposition(
                page=page,
                page_number=page_number,
            )

        photo_settings = (
            photo_settings
            or PhotoPageSettings(
                template_id=page.template_id
            )
        )

        layout = self._registry.get(
            page.template_id
        )

        return layout.compose(
            page,
            photo_settings,
            page_numbers,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            reserved_caption_lines=reserved_caption_lines,
        )
