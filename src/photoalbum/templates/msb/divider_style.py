from __future__ import annotations

from math import isfinite

from photoalbum.rendering.fonts import resolve_font_family


def divider_font_family(settings: dict, section: str, fallback: str) -> str:
    value = settings.get(section, {})
    if not isinstance(value, dict):
        value = {}
    requested = value.get("title_font_family")
    return resolve_font_family(
        str(requested) if requested is not None else None,
        fallback=fallback,
    )


def divider_font_size(settings: dict, section: str, default: float = 72.0) -> float:
    value = settings.get(section, {})
    if not isinstance(value, dict):
        return default
    try:
        size = float(value.get("title_font_size", default))
    except (TypeError, ValueError):
        return default
    return size if isfinite(size) and 1 <= size <= 300 else default
