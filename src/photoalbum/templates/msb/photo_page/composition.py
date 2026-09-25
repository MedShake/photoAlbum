"""MSB photo captions and their physical layout."""
from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from photoalbum.album.composition import (
    ImageFit, NormalizedRect, PageComposition, PageNumberComposition,
    PhotoSlotComposition, compose_page_number,
)
from photoalbum.album.pagination import PlannedPage
from photoalbum.album.settings import PageInstance, PhotoPageSettings, PageNumberSettings
from photoalbum.geocoding.location_caption_builder import LocationCaptionBuilder
from photoalbum.models import Photo
from .caption_style import caption_show_datetime, caption_show_location

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

    if caption_show_datetime(settings.page.settings):
        capture_datetime = photo.capture_datetime

    if caption_show_location(settings.page.settings):
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
        instance: PageInstance,
        page_numbers: PageNumberSettings,
        *,
        page_width_mm: float = 210.0,
        page_height_mm: float = 297.0,
        reserved_caption_lines: int | None = None,
    ) -> PageComposition:
        photo_settings = PhotoPageSettings(page=instance)
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


    def required_caption_lines(self, page, instance, *, page_width_mm, page_height_mm):
        settings = PhotoPageSettings(page=instance)
        cells = self.cells_factory(page_width_mm, page_height_mm)
        return max((self._required_caption_lines(
            build_photo_caption(photo, settings), cell,
            settings=settings.page.settings, page_width_mm=page_width_mm,
        ) for photo, cell in zip(page.photos, cells)), default=0)

    def reserve_caption_lines(self, required):
        return min(required, self.max_caption_lines)
