"""Format-aware manual menu variants. Declaration order drives automatic round-robin."""
from __future__ import annotations

LARGE_FIRST = "large-first"
LARGE_LAST = "large-last"
FOUR_CURRENT = "four-current"
FOUR_CURRENT_MIRROR = "four-current-mirror"
FOUR_TOP_MEDIUM_LEFT = "four-top-medium-left"
FOUR_TOP_MEDIUM_RIGHT = "four-top-medium-right"
FIVE_MOSAIC_LEFT = "five-mosaic-left"
FIVE_MOSAIC_RIGHT = "five-mosaic-right"
FIVE_SEQUENCE_TOP = "five-sequence-top"
FIVE_SEQUENCE_CENTER = "five-sequence-center"
FIVE_SEQUENCE_BOTTOM = "five-sequence-bottom"

FIVE_BY_FAMILY = {'portrait': ('five-mosaic-double-left-pll', 'five-mosaic-left', 'five-mosaic-double-left-llp', 'five-mosaic-triple-left-pll', 'five-mosaic-right', 'five-mosaic-triple-left-llp', 'five-sequence-top', 'five-sequence-center', 'five-sequence-bottom'), 'landscape': ('five-mosaic-left', 'five-mosaic-columns-acb', 'five-mosaic-columns-bac', 'five-mosaic-columns-bca', 'five-mosaic-columns-cab', 'five-mosaic-right', 'five-sequence-top', 'five-sequence-bottom'), 'square': ('five-mosaic-left', 'five-mosaic-square-3top-ppl-lp', 'five-mosaic-square-3top-plp-pl', 'five-mosaic-square-3top-plp-lp', 'five-mosaic-square-3top-lpp-pl', 'five-mosaic-right', 'five-mosaic-square-2top-pl-ppl', 'five-mosaic-square-2top-lp-ppl', 'five-mosaic-square-2top-pl-plp', 'five-mosaic-square-2top-lp-plp', 'five-mosaic-square-2top-pl-lpp', 'five-mosaic-square-2top-lp-lpp')}


def page_family(width_mm: float, height_mm: float) -> str:
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("Page dimensions must be positive")
    if abs(width_mm-height_mm) <= 0.01*max(width_mm,height_mm):
        return "square"
    return "landscape" if width_mm > height_mm else "portrait"


def variants_for(capacity: int, width_mm: float, height_mm: float) -> tuple[str, ...]:
    family = page_family(width_mm, height_mm)
    if capacity == 3:
        return (LARGE_FIRST,LARGE_LAST)
    if capacity == 4:
        if family == "square": return (FOUR_CURRENT,FOUR_CURRENT_MIRROR)
        return (FOUR_CURRENT,FOUR_TOP_MEDIUM_LEFT,FOUR_TOP_MEDIUM_RIGHT,FOUR_CURRENT_MIRROR)
    if capacity == 5:
        return FIVE_BY_FAMILY[family]
    return ()


def default_variant(capacity: int,width_mm:float,height_mm:float)->str|None:
    options=variants_for(capacity,width_mm,height_mm)
    return options[0] if options else None


def validated_variant(capacity:int,width_mm:float,height_mm:float,selected:str|None)->str|None:
    options=variants_for(capacity,width_mm,height_mm)
    if not options:return None
    return selected if selected in options else options[0]
