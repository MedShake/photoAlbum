"""MSB automatic photo-page selection based on page and photo orientation."""
from __future__ import annotations

from photoalbum.models import displayed_photo_dimensions
from photoalbum.album import AutomaticPhotoPageContext, PageInstance

from .variants import LAYOUT_LARGE_FIRST, LAYOUT_LARGE_LAST


MODE_ID = "msb-orientation-1-2"
MODE_ID_1_2_3 = "msb-orientation-1-2-3"


def _orientation(photo) -> str | None:
    dimensions = displayed_photo_dimensions(photo)
    if dimensions is None:
        return None
    width, height = dimensions
    if width == height:
        return None
    return "landscape" if width > height else "portrait"


def _page_orientation(context: AutomaticPhotoPageContext) -> str | None:
    if context.page_width_mm == context.page_height_mm:
        return None
    return (
        "landscape"
        if context.page_width_mm > context.page_height_mm
        else "portrait"
    )


def select_orientation_template(context: AutomaticPhotoPageContext) -> str:
    """Select the existing MSB 1/2 mode.

    Landscape pages group two consecutive portrait photos. Portrait pages group
    two consecutive landscape photos. Square/unknown photos stay alone.
    """
    page_orientation = _page_orientation(context)
    if page_orientation is None or len(context.photos) < 2:
        return "photo-page-1"

    first = _orientation(context.photos[0])
    second = _orientation(context.photos[1])
    opposite = "portrait" if page_orientation == "landscape" else "landscape"

    if first == opposite and second == opposite:
        return "photo-page-2"
    return "photo-page-1"


def select_orientation_1_2_3_template(
    context: AutomaticPhotoPageContext,
) -> str | PageInstance:
    """Choose a three-photo layout variant without reordering the photo stream.

    The returned PageInstance carries the layout selected for this occurrence.
    The pagination engine merges that variant with the user's shared settings.
    Other modes and the historical 1/2 fallback remain unchanged.
    """
    page_orientation = _page_orientation(context)
    if page_orientation is None:
        return "photo-page-1"

    if len(context.photos) >= 3:
        orientations = tuple(_orientation(photo) for photo in context.photos[:3])
        if page_orientation == "portrait":
            patterns = {
                ("landscape", "portrait", "portrait"): LAYOUT_LARGE_FIRST,
                ("portrait", "portrait", "landscape"): LAYOUT_LARGE_LAST,
            }
        else:
            patterns = {
                ("portrait", "landscape", "landscape"): LAYOUT_LARGE_FIRST,
                ("landscape", "landscape", "portrait"): LAYOUT_LARGE_LAST,
            }
        variant = patterns.get(orientations)
        if variant is not None:
            return PageInstance(
                "photo-page-3", settings={"layout_variant": variant},
            )

    return select_orientation_template(context)
