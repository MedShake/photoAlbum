"""Automatic Complex layout: find the largest compatible chronological prefix.

Only the first N photos may be used.  The selector NEVER reorders photos,
never recrops, and never crosses the boundary supplied by PaginationEngine.
Layout signatures come from the SAME geometries exposed by the manual menu.
"""
from __future__ import annotations

from photoalbum.album import AutomaticPhotoPageContext, PageInstance
from photoalbum.models import displayed_photo_dimensions

from .geometry import DATA
from .variants import LARGE_FIRST, LARGE_LAST, page_family, variants_for

MODE_ID = "complex-auto-1-5"


def photo_orientation(photo) -> str | None:
    """P or L after EXIF orientation; square/invalid/unknown require single photo."""
    dims = displayed_photo_dimensions(photo)
    if not dims:
        return None
    width, height = dims
    if width <= 0 or height <= 0:
        return None
    if abs(width - height) <= .01 * max(width, height):
        return None
    return "P" if width < height else "L"


def signature(capacity: int, variant: str | None, family: str) -> tuple[str, ...]:
    """Ordered photo orientations that actually match the reference geometry."""
    if capacity in (4, 5):
        # Each slot is stored in CHRONOLOGICAL PHOTO ORDER, not display order.
        # Left/right reading rules are therefore encoded by the geometry itself.
        reference = DATA["families"][family]["layouts"][variant]
        return tuple("P" if item["ratio"] == "3:4" else "L" for item in reference)
    if capacity == 3:
        main_first = ("P", "L", "L") if family == "landscape" else ("L", "P", "P")
        if variant == LARGE_FIRST:
            return main_first
        if variant == LARGE_LAST:
            return main_first[::-1]
        raise ValueError(f"Unsupported Complex three-photo variant: {variant}")
    if capacity == 2:
        # The 2-photo geometry is one row (two portraits) in landscape,
        # otherwise two horizontal images, one above the other.
        return ("P", "P") if family == "landscape" else ("L", "L")
    if capacity == 1:
        return ("*",)  # final unconditional fallback
    raise ValueError(f"Unsupported photo capacity: {capacity}")


def compatible_options(capacity: int, family: str, pattern: tuple[str | None, ...]):
    """List of matching variants, respecting the actual format's allowed menu."""
    if len(pattern) < capacity:
        return ()
    options = variants_for(capacity, 297, 210) if family == "landscape" else (
        variants_for(capacity, 210, 210) if family == "square" else variants_for(capacity, 210, 297)
    )
    options = options or (None,)
    return tuple(
        opt for opt in options
        if capacity == 1 or signature(capacity, opt, family) == pattern[:capacity]
    )


def select_automatic_1_5(context: AutomaticPhotoPageContext) -> str | PageInstance:
    """Try 5,4,3,2 then 1; never sacrifice a compatible photo to a smaller template.

    If the host supplies selection_counts (Photo Album integration for Complex 1.4),
    matching variants rotate in manual declaration order. The host creates a
    fresh count map per pagination and skips this selector for manual overrides.
    """
    family = page_family(context.page_width_mm, context.page_height_mm)
    remaining = tuple(context.photos[:5])
    patterns = tuple(photo_orientation(photo) for photo in remaining)
    for capacity in range(min(5, len(remaining)), 1, -1):
        options = compatible_options(capacity, family, patterns)
        if not options:
            continue
        # Only an actual automatic page advances a shared rotation. A plain
        # selector call (older host, isolated preview) has NO persistent effect.
        variant = options[0]
        counts = getattr(context, "selection_counts", None)
        if counts is not None and len(options) > 1:
            key = (family, "".join(patterns[:capacity]))
            index = counts.get(key, 0)
            variant = options[index % len(options)]
            counts[key] = index + 1
        if variant is None:
            return f"complex-photo-{capacity}"
        return PageInstance(
            template_id=f"complex-photo-{capacity}",
            settings={"layout_variant": variant},
        )
    return "complex-photo-1"
