"""MSB photo geometry and caption metrics, shared by preview and PDF."""
from __future__ import annotations

from photoalbum.album.composition import (
    NormalizedRect, PhotoTemplateLayout, TemplateLayoutRegistry,
)


def _grid_cells(
    *,
    rows: int,
    columns: int,
    capacity: int,
    page_width_mm: float,
    page_height_mm: float,
    margin_mm: float = 10.0,
    vertical_margin_mm: float | None = None,
    top_margin_mm: float | None = None,
    bottom_margin_mm: float | None = None,
    horizontal_gap_mm: float = 8.0,
    vertical_gap_mm: float = 8.0,
) -> tuple[NormalizedRect, ...]:
    margin_x = margin_mm / page_width_mm

    default_vertical_margin = (
        margin_mm
        if vertical_margin_mm is None
        else vertical_margin_mm
    )

    margin_top = (
        default_vertical_margin
        if top_margin_mm is None
        else top_margin_mm
    ) / page_height_mm

    margin_bottom = (
        default_vertical_margin
        if bottom_margin_mm is None
        else bottom_margin_mm
    ) / page_height_mm

    horizontal_gap = (
        horizontal_gap_mm / page_width_mm
    )

    vertical_gap = (
        vertical_gap_mm / page_height_mm
    )

    available_width = (
        1
        - 2 * margin_x
        - (columns - 1) * horizontal_gap
    )

    available_height = (
        1
        - margin_top
        - margin_bottom
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
                    margin_x
                    + column
                    * (
                        cell_width
                        + horizontal_gap
                    )
                ),
                y=(
                    margin_top
                    + row
                    * (
                        cell_height
                        + vertical_gap
                    )
                ),
                width=cell_width,
                height=cell_height,
            )
        )

    return tuple(cells)


def _photo_page_1_cells(
    page_width_mm: float,
    page_height_mm: float,
) -> tuple[NormalizedRect, ...]:
    return _grid_cells(
        rows=1,
        columns=1,
        capacity=1,
        page_width_mm=page_width_mm,
        page_height_mm=page_height_mm,
        top_margin_mm=6.0,
        bottom_margin_mm=12.0,
        vertical_gap_mm=4.0,
    )


def _photo_page_2_cells(
    page_width_mm: float,
    page_height_mm: float,
) -> tuple[NormalizedRect, ...]:
    return _grid_cells(
        rows=2,
        columns=1,
        capacity=2,
        page_width_mm=page_width_mm,
        page_height_mm=page_height_mm,
        top_margin_mm=6.0,
        bottom_margin_mm=12.0,
        vertical_gap_mm=4.0,
    )


def _photo_page_3_cells(
    page_width_mm: float,
    page_height_mm: float,
) -> tuple[NormalizedRect, ...]:
    margin_x = 10.0 / page_width_mm
    margin_top = 6.0 / page_height_mm
    margin_bottom = 12.0 / page_height_mm

    horizontal_gap = (
        8.0 / page_width_mm
    )

    vertical_gap = (
        4.0 / page_height_mm
    )

    available_height = (
        1
        - margin_top
        - margin_bottom
        - vertical_gap
    )

    # Keep the historical visual hierarchy:
    # one large photograph above two smaller ones.
    top_height = (
        available_height * 0.48
    )

    bottom_height = (
        available_height - top_height
    )

    bottom_y = (
        margin_top
        + top_height
        + vertical_gap
    )

    available_width = (
        1
        - 2 * margin_x
        - horizontal_gap
    )

    bottom_width = (
        available_width / 2
    )

    return (
        NormalizedRect(
            x=margin_x,
            y=margin_top,
            width=1 - 2 * margin_x,
            height=top_height,
        ),
        NormalizedRect(
            x=margin_x,
            y=bottom_y,
            width=bottom_width,
            height=bottom_height,
        ),
        NormalizedRect(
            x=(
                margin_x
                + bottom_width
                + horizontal_gap
            ),
            y=bottom_y,
            width=bottom_width,
            height=bottom_height,
        ),
    )

def _photo_page_4_cells(
    page_width_mm: float,
    page_height_mm: float,
) -> tuple[NormalizedRect, ...]:
    return _grid_cells(
        rows=2,
        columns=2,
        capacity=4,
        page_width_mm=page_width_mm,
        page_height_mm=page_height_mm,
        top_margin_mm=6.0,
        bottom_margin_mm=12.0,
        vertical_gap_mm=4.0,
    )


def register_layouts(registry: TemplateLayoutRegistry) -> None:
    from .caption_layout import (
        physical_line_height_mm,
        required_line_count,
    )

    def count_caption_lines(content, settings, width_mm):
        return required_line_count(
            content, width_mm=width_mm, settings=settings
        )

    registry.register(
        "photo-page-1",
        PhotoTemplateLayout(
            cells_factory=_photo_page_1_cells,
            max_caption_lines=3,
            caption_line_counter=count_caption_lines,
            caption_line_height_counter=physical_line_height_mm,
        ),
    )

    registry.register(
        "photo-page-2",
        PhotoTemplateLayout(
            cells_factory=_photo_page_2_cells,
            max_caption_lines=3,
            caption_line_counter=count_caption_lines,
            caption_line_height_counter=physical_line_height_mm,
        ),
    )

    registry.register(
        "photo-page-3",
        PhotoTemplateLayout(
            cells_factory=_photo_page_3_cells,
            max_caption_lines=3,
            caption_line_counter=count_caption_lines,
            caption_line_height_counter=physical_line_height_mm,
        ),
    )

    registry.register(
        "photo-page-4",
        PhotoTemplateLayout(
            cells_factory=_photo_page_4_cells,
            max_caption_lines=3,
            caption_line_counter=count_caption_lines,
            caption_line_height_counter=physical_line_height_mm,
        ),
    )
