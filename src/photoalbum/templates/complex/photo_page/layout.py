"""Complex photo geometry and caption-aware composition."""
from __future__ import annotations

from photoalbum.album.composition import ImageFit, NormalizedRect, PageComposition, PhotoSlotComposition
from photoalbum.album.composition import TemplateLayoutRegistry
from .composition import PhotoTemplateLayout
from .caption_layout import physical_line_height_mm, required_line_count
from .variants import (
    LARGE_FIRST, LARGE_LAST,
    page_family, validated_variant,
)
from .geometry import DATA as _DATA

_CAPTION_MM = float(_DATA["caption_reserve_mm"])


def _grid_cells(*, rows:int, columns:int, capacity:int, page_width_mm:float, page_height_mm:float,
                margin_mm:float=10.0, vertical_margin_mm:float|None=None, top_margin_mm:float|None=None,
                bottom_margin_mm:float|None=None, horizontal_gap_mm:float=8.0, vertical_gap_mm:float=8.0) -> tuple[NormalizedRect, ...]:
    margin_x = margin_mm / page_width_mm
    default_vertical_margin = margin_mm if vertical_margin_mm is None else vertical_margin_mm
    margin_top = (default_vertical_margin if top_margin_mm is None else top_margin_mm) / page_height_mm
    margin_bottom = (default_vertical_margin if bottom_margin_mm is None else bottom_margin_mm) / page_height_mm
    horizontal_gap = horizontal_gap_mm / page_width_mm
    vertical_gap = vertical_gap_mm / page_height_mm
    available_width = 1 - 2 * margin_x - (columns - 1) * horizontal_gap
    available_height = 1 - margin_top - margin_bottom - (rows - 1) * vertical_gap
    cell_width = available_width / columns
    cell_height = available_height / rows
    cells = []
    for index in range(capacity):
        row = index // columns
        column = index % columns
        cells.append(NormalizedRect(
            x=margin_x + column * (cell_width + horizontal_gap),
            y=margin_top + row * (cell_height + vertical_gap),
            width=cell_width, height=cell_height,
        ))
    return tuple(cells)


def _photo_page_1_cells(page_width_mm: float, page_height_mm: float) -> tuple[NormalizedRect, ...]:
    return _grid_cells(rows=1, columns=1, capacity=1, page_width_mm=page_width_mm, page_height_mm=page_height_mm,
                       top_margin_mm=6.0, bottom_margin_mm=12.0, vertical_gap_mm=4.0)


def _photo_page_2_cells(page_width_mm: float, page_height_mm: float) -> tuple[NormalizedRect, ...]:
    is_landscape = page_width_mm > page_height_mm
    return _grid_cells(rows=1 if is_landscape else 2, columns=2 if is_landscape else 1, capacity=2,
                       page_width_mm=page_width_mm, page_height_mm=page_height_mm,
                       top_margin_mm=6.0, bottom_margin_mm=12.0, horizontal_gap_mm=8.0, vertical_gap_mm=4.0)


def _photo_page_3_cells(page_width_mm: float, page_height_mm: float, variant: str = LARGE_FIRST) -> tuple[NormalizedRect, ...]:
    margin_x = 10.0 / page_width_mm
    margin_top = 6.0 / page_height_mm
    margin_bottom = 12.0 / page_height_mm
    horizontal_gap = 8.0 / page_width_mm
    vertical_gap = 4.0 / page_height_mm
    is_landscape = page_width_mm > page_height_mm
    if is_landscape:
        available_width = 1 - 2 * margin_x - horizontal_gap
        left_width = available_width * 0.48
        right_width = available_width - left_width
        right_x = margin_x + left_width + horizontal_gap
        available_height = 1 - margin_top - margin_bottom - vertical_gap
        right_height = available_height / 2
        lower_y = margin_top + right_height + vertical_gap
        cells = (
            NormalizedRect(x=margin_x, y=margin_top, width=left_width, height=1 - margin_top - margin_bottom),
            NormalizedRect(x=right_x, y=margin_top, width=right_width, height=right_height),
            NormalizedRect(x=right_x, y=lower_y, width=right_width, height=right_height),
        )
        if variant == LARGE_LAST:
            large_x = margin_x + right_width + horizontal_gap
            return (
                NormalizedRect(margin_x, margin_top, right_width, right_height),
                NormalizedRect(margin_x, lower_y, right_width, right_height),
                NormalizedRect(large_x, margin_top, left_width, 1 - margin_top - margin_bottom),
            )
        return cells
    available_height = 1 - margin_top - margin_bottom - vertical_gap
    top_height = available_height * 0.48
    bottom_height = available_height - top_height
    bottom_y = margin_top + top_height + vertical_gap
    available_width = 1 - 2 * margin_x - horizontal_gap
    bottom_width = available_width / 2
    cells = (
        NormalizedRect(x=margin_x, y=margin_top, width=1 - 2 * margin_x, height=top_height),
        NormalizedRect(x=margin_x, y=bottom_y, width=bottom_width, height=bottom_height),
        NormalizedRect(x=margin_x + bottom_width + horizontal_gap, y=bottom_y, width=bottom_width, height=bottom_height),
    )
    if variant == LARGE_LAST:
        large_bottom_y = margin_top + bottom_height + vertical_gap
        return (
            NormalizedRect(margin_x, margin_top, bottom_width, bottom_height),
            NormalizedRect(margin_x + bottom_width + horizontal_gap, margin_top, bottom_width, bottom_height),
            NormalizedRect(margin_x, large_bottom_y, 1 - 2 * margin_x, top_height),
        )
    return cells


def _photo_page_3_cells_for_settings(page_width_mm: float, page_height_mm: float, settings: dict) -> tuple[NormalizedRect, ...]:
    return _photo_page_3_cells(page_width_mm, page_height_mm, variant=settings.get("layout_variant", LARGE_FIRST))


def _rects_for(capacity: int, width_mm: float, height_mm: float, settings: dict) -> tuple[NormalizedRect, ...]:
    family = page_family(width_mm, height_mm)
    variant = validated_variant(capacity, width_mm, height_mm, settings.get("layout_variant"))
    definition = _DATA["families"][family]
    reference = definition["layouts"][variant]
    if len(reference) != capacity:
        raise ValueError("Unexpected Complex geometry capacity")
    ref_w, ref_h = definition["page_width_mm"], definition["page_height_mm"]
    factor = min(width_mm / ref_w, height_mm / ref_h)
    offset_x = (width_mm - ref_w * factor) / 2
    offset_y = (height_mm - ref_h * factor) / 2
    result = []
    for item in reference:
        x = (offset_x + item["x"] * factor) / width_mm
        y = (offset_y + item["y"] * factor) / height_mm
        w = item["w"] * factor / width_mm
        h = (item["h"] + _CAPTION_MM) * factor / height_mm
        result.append(NormalizedRect(x, y, w, h))
    return tuple(result)


def _caption_line_count(content, settings, width_mm):
    return required_line_count(content, width_mm=width_mm, settings=settings)


class ComplexPhotoLayout(PhotoTemplateLayout):
    def compose(self, page, instance, page_numbers, *, page_width_mm=210.0, page_height_mm=297.0, reserved_caption_lines=None):
        required = self.required_caption_lines(page, instance, page_width_mm=page_width_mm, page_height_mm=page_height_mm)
        lines = max(1, min(self.max_caption_lines, max(required, reserved_caption_lines or 0)))
        result = super().compose(page, instance, page_numbers, page_width_mm=page_width_mm, page_height_mm=page_height_mm, reserved_caption_lines=lines)
        adjusted = tuple(PhotoSlotComposition(
            image_rect=slot.image_rect,
            caption_rect=(None if slot.caption.is_empty else slot.caption_rect),
            caption=slot.caption,
            image_fit=ImageFit.CONTAIN,
            required_caption_lines=slot.required_caption_lines,
            max_caption_lines=slot.max_caption_lines,
        ) for slot in result.photo_slots)
        return PageComposition(page=result.page, photo_slots=adjusted, page_number=result.page_number)


def register_layouts(registry: TemplateLayoutRegistry) -> None:
    registry.register("complex-photo-1", PhotoTemplateLayout(
        cells_factory=_photo_page_1_cells, max_caption_lines=3,
        caption_line_counter=_caption_line_count, caption_line_height_counter=physical_line_height_mm,
        image_fit=ImageFit.CONTAIN,
    ))
    registry.register("complex-photo-2", PhotoTemplateLayout(
        cells_factory=_photo_page_2_cells, max_caption_lines=3,
        caption_line_counter=_caption_line_count, caption_line_height_counter=physical_line_height_mm,
        image_fit=ImageFit.CONTAIN,
    ))
    registry.register("complex-photo-3", PhotoTemplateLayout(
        cells_factory=_photo_page_3_cells, settings_cells_factory=_photo_page_3_cells_for_settings,
        max_caption_lines=3, caption_line_counter=_caption_line_count,
        caption_line_height_counter=physical_line_height_mm, image_fit=ImageFit.CONTAIN,
    ))
    for capacity in (4, 5):
        registry.register(f"complex-photo-{capacity}", ComplexPhotoLayout(
            cells_factory=lambda w, h, n=capacity: _rects_for(n, w, h, {}),
            settings_cells_factory=lambda w, h, settings, n=capacity: _rects_for(n, w, h, settings),
            max_caption_lines=3, caption_line_counter=_caption_line_count,
            caption_line_height_counter=physical_line_height_mm, image_fit=ImageFit.CONTAIN,
        ))
