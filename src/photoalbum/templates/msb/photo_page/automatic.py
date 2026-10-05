"""MSB automatic photo-page selection based on page and photo orientation."""
from __future__ import annotations

from photoalbum.models import displayed_photo_dimensions
from photoalbum.album import AutomaticPhotoPageContext


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
) -> str:
    """Prefer MSB's orientation-aware 3-photo layout, then 2, then 1.

    For a portrait page, the 3-photo layout expects landscape / portrait /
    portrait: one wide photo on top and two portrait photos below.

    For a landscape page, it expects portrait / landscape / landscape: one
    tall photo on the left and two landscape photos stacked on the right.

    If that exact three-photo pattern is unavailable, the existing 1/2 rule
    is used unchanged.
    """
    page_orientation = _page_orientation(context)
    if page_orientation is None:
        return "photo-page-1"

    if len(context.photos) >= 3:
        orientations = tuple(_orientation(photo) for photo in context.photos[:3])
        expected = (
            ("portrait", "landscape", "landscape")
            if page_orientation == "landscape"
            else ("landscape", "portrait", "portrait")
        )
        if orientations == expected:
            return "photo-page-3"

    return select_orientation_template(context)
