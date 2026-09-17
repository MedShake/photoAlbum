from math import isfinite

from photoalbum.rendering.fonts import resolve_font_family


def title_font_family(settings: dict) -> str:
    """Return the configured title font family."""
    scatter = settings.get("scatter", {})
    if not isinstance(scatter, dict):
        return resolve_font_family(None)

    value = scatter.get("title_font_family")
    requested = str(value) if value is not None else None
    return resolve_font_family(requested)


def title_font_size(settings: dict, title: str) -> float:
    """Return the title size in typographic points."""
    title = title.strip()
    if len(title) == 4 and title.isdigit():
        default = 72
    elif (len(title) == 9 and title[4] in ('-', '–')
          and title[:4].isdigit() and title[5:].isdigit()):
        default = 52
    else:
        default = 44
    scatter = settings.get('scatter', {})
    if not isinstance(scatter, dict):
        return default
    try:
        value = float(scatter.get('title_font_size', default))
    except (TypeError, ValueError):
        return default
    return value if isfinite(value) and 1 <= value <= 300 else default
