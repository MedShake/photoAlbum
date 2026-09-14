from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

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

    @property
    def line_count(self) -> int:
        return int(self.capture_datetime is not None) + int(
            bool(self.location_text)
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
    Build the best available human-readable location.

    Prefer a named place, optionally complemented by the city.
    Fall back to city, then address.
    """

    place = (
        photo.place_name.strip()
        if photo.place_name
        else None
    )
    city = (
        photo.city.strip()
        if photo.city
        else None
    )
    address = (
        photo.address.strip()
        if photo.address
        else None
    )

    if place and city:
        if place.casefold() == city.casefold():
            return place

        return f"{place}, {city}"

    if place:
        return place

    if city:
        return city

    if address:
        return address

    return None


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

    return PhotoCaptionContent(
        capture_datetime=capture_datetime,
        location_text=location_text,
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


@dataclass(frozen=True)
class PhotoTemplateLayout:
    cells: tuple[NormalizedRect, ...]
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
    ) -> PageComposition:
        captions = tuple(
            build_photo_caption(
                photo,
                photo_settings,
            )
            for photo in page.photos
        )

        row_caption_lines = self._row_caption_lines(
            captions
        )

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
            )
            for index, cell in enumerate(self.cells)
        )

        page_number = None

        if page_numbers.enabled:
            page_number = self._page_number(page)

        return PageComposition(
            page=page,
            photo_slots=slots,
            page_number=page_number,
        )

    def _row_caption_lines(
        self,
        captions: tuple[PhotoCaptionContent, ...],
    ) -> dict[float, int]:
        result: dict[float, int] = {}

        for index, cell in enumerate(self.cells):
            key = self._row_key(cell)

            lines = (
                captions[index].line_count
                if index < len(captions)
                else 0
            )

            result[key] = max(
                result.get(key, 0),
                lines,
            )

        return result

    @staticmethod
    def _row_key(
        cell: NormalizedRect,
    ) -> float:
        return round(cell.y, 6)

    def _compose_slot(
        self,
        *,
        cell: NormalizedRect,
        caption: PhotoCaptionContent,
        reserved_lines: int,
    ) -> PhotoSlotComposition:
        if reserved_lines <= 0:
            return PhotoSlotComposition(
                image_rect=cell,
                caption_rect=None,
                caption=caption,
                image_fit=self.image_fit,
            )

        caption_height = (
            self.caption_line_height
            * reserved_lines
        )

        image_height = (
            cell.height
            - caption_height
            - self.image_caption_gap
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
                + self.image_caption_gap
            ),
            width=cell.width,
            height=caption_height,
        )

        return PhotoSlotComposition(
            image_rect=image_rect,
            caption_rect=caption_rect,
            caption=caption,
            image_fit=self.image_fit,
        )

    def _page_number(
        self,
        page: PlannedPage,
    ) -> PageNumberComposition:
        if page.side == PageSide.LEFT:
            x = self.page_number_outer_margin
            alignment = HorizontalAlignment.LEFT
        else:
            x = (
                1
                - self.page_number_outer_margin
                - self.page_number_width
            )
            alignment = HorizontalAlignment.RIGHT

        return PageNumberComposition(
            number=page.number,
            rect=NormalizedRect(
                x=x,
                y=self.page_number_y,
                width=self.page_number_width,
                height=self.page_number_height,
            ),
            alignment=alignment,
        )


def _grid_cells(
    *,
    rows: int,
    columns: int,
    capacity: int,
    margin: float,
    horizontal_gap: float,
    vertical_gap: float,
) -> tuple[NormalizedRect, ...]:
    available_width = (
        1
        - 2 * margin
        - (columns - 1) * horizontal_gap
    )

    available_height = (
        1
        - 2 * margin
        - (rows - 1) * vertical_gap
    )

    cell_width = available_width / columns
    cell_height = available_height / rows

    cells: list[NormalizedRect] = []

    for index in range(capacity):
        row = index // columns
        column = index % columns

        cells.append(
            NormalizedRect(
                x=(
                    margin
                    + column
                    * (cell_width + horizontal_gap)
                ),
                y=(
                    margin
                    + row
                    * (cell_height + vertical_gap)
                ),
                width=cell_width,
                height=cell_height,
            )
        )

    return tuple(cells)


def create_builtin_layout_registry(
) -> TemplateLayoutRegistry:
    registry = TemplateLayoutRegistry()

    margin = 0.06
    horizontal_gap = 0.04
    vertical_gap = 0.04

    registry.register(
        "photo-page-1",
        PhotoTemplateLayout(
            cells=(
                NormalizedRect(
                    x=margin,
                    y=margin,
                    width=1 - 2 * margin,
                    height=1 - 2 * margin,
                ),
            )
        ),
    )

    registry.register(
        "photo-page-2",
        PhotoTemplateLayout(
            cells=_grid_cells(
                rows=2,
                columns=1,
                capacity=2,
                margin=margin,
                horizontal_gap=horizontal_gap,
                vertical_gap=vertical_gap,
            )
        ),
    )

    three_top = NormalizedRect(
        x=margin,
        y=margin,
        width=1 - 2 * margin,
        height=0.40,
    )

    bottom_y = (
        three_top.y
        + three_top.height
        + vertical_gap
    )

    bottom_height = 1 - margin - bottom_y

    bottom_width = (
        1
        - 2 * margin
        - horizontal_gap
    ) / 2

    registry.register(
        "photo-page-3",
        PhotoTemplateLayout(
            cells=(
                three_top,
                NormalizedRect(
                    x=margin,
                    y=bottom_y,
                    width=bottom_width,
                    height=bottom_height,
                ),
                NormalizedRect(
                    x=(
                        margin
                        + bottom_width
                        + horizontal_gap
                    ),
                    y=bottom_y,
                    width=bottom_width,
                    height=bottom_height,
                ),
            )
        ),
    )

    registry.register(
        "photo-page-4",
        PhotoTemplateLayout(
            cells=_grid_cells(
                rows=2,
                columns=2,
                capacity=4,
                margin=margin,
                horizontal_gap=horizontal_gap,
                vertical_gap=vertical_gap,
            )
        ),
    )

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

    def compose(
        self,
        page: PlannedPage,
        photo_settings: PhotoPageSettings | None = None,
        page_numbers: PageNumberSettings | None = None,
    ) -> PageComposition:
        if (
            page.kind != PlanItemKind.PHOTO_GROUP
            or page.photo_capacity <= 0
            or page.template_id is None
        ):
            return PageComposition(page=page)

        photo_settings = (
            photo_settings
            or PhotoPageSettings(
                template_id=page.template_id
            )
        )

        page_numbers = (
            page_numbers
            or PageNumberSettings()
        )

        layout = self._registry.get(
            page.template_id
        )

        return layout.compose(
            page,
            photo_settings,
            page_numbers,
        )
