"""MSB automatic selection between its one- and two-photo layouts."""
from __future__ import annotations

from photoalbum.models import displayed_photo_dimensions
from photoalbum.album import AutomaticPhotoPageContext


MODE_ID = "msb-orientation-1-2"


def select_orientation_template(context: AutomaticPhotoPageContext) -> str:
    if context.page_width_mm == context.page_height_mm or len(context.photos) < 2:
        return "photo-page-1"

    dimensions = [displayed_photo_dimensions(photo) for photo in context.photos[:2]]
    if any(item is None or item[0] == item[1] for item in dimensions):
        return "photo-page-1"

    if context.page_width_mm > context.page_height_mm:
        group = all(width < height for width, height in dimensions if dimensions)
    else:
        group = all(width > height for width, height in dimensions if dimensions)
    return "photo-page-2" if group else "photo-page-1"
