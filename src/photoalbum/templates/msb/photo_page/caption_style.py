from __future__ import annotations

from math import isfinite

from PySide6.QtGui import QColor

from photoalbum.rendering.fonts import resolve_font_family


DEFAULT_CAPTION_ORDER = (
    "caption",
    "datetime",
    "break",
    "location",
)
DEFAULT_CAPTION_FONT_SIZE = 8.0
DEFAULT_CAPTION_COLOR = "#000000"


def _local(settings: dict) -> dict:
    value = settings.get("photo_caption", {})
    return value if isinstance(value, dict) else {}


def caption_show_user(settings: dict) -> bool:
    return bool(_local(settings).get("show_caption", True))


def caption_show_datetime(settings: dict) -> bool:
    return bool(_local(settings).get("show_datetime", True))


def caption_show_location(settings: dict) -> bool:
    return bool(_local(settings).get("show_location", True))


def caption_font_family(settings: dict) -> str:
    value = _local(settings).get("font_family")
    requested = str(value) if value else None
    return resolve_font_family(requested)


def caption_font_size(settings: dict) -> float:
    try:
        value = float(
            _local(settings).get(
                "font_size",
                DEFAULT_CAPTION_FONT_SIZE,
            )
        )
    except (TypeError, ValueError):
        return DEFAULT_CAPTION_FONT_SIZE

    if not isfinite(value) or not 1 <= value <= 300:
        return DEFAULT_CAPTION_FONT_SIZE

    return value


def caption_color(settings: dict) -> QColor:
    value = str(
        _local(settings).get(
            "color",
            DEFAULT_CAPTION_COLOR,
        )
    )
    color = QColor(value)
    if not color.isValid():
        color = QColor(DEFAULT_CAPTION_COLOR)
    return color


def caption_color_name(settings: dict) -> str:
    return caption_color(settings).name()


def caption_order(settings: dict) -> tuple[str, ...]:
    raw = _local(settings).get(
        "order",
        list(DEFAULT_CAPTION_ORDER),
    )

    if not isinstance(raw, (list, tuple)):
        return DEFAULT_CAPTION_ORDER

    allowed = set(DEFAULT_CAPTION_ORDER)
    result: list[str] = []

    for item in raw:
        value = str(item)
        if value in allowed and value not in result:
            result.append(value)

    # Migration/repair: never lose an item merely because an older
    # project did not know about it.
    for value in DEFAULT_CAPTION_ORDER:
        if value not in result:
            result.append(value)

    return tuple(result)


def caption_lines(
    *,
    caption_text: str | None,
    capture_datetime_text: str | None,
    location_text: str | None,
    settings: dict,
) -> list[str]:
    values = {
        "caption": (
            caption_text
            if caption_show_user(settings)
            and caption_text
            else None
        ),
        "datetime": (
            capture_datetime_text
            if caption_show_datetime(settings)
            and capture_datetime_text
            else None
        ),
        "location": (
            location_text
            if caption_show_location(settings)
            and location_text
            else None
        ),
    }

    lines: list[list[str]] = [[]]

    for item in caption_order(settings):
        if item == "break":
            # A movable break affects layout, but must not create
            # gratuitous empty lines at either end.
            if lines[-1]:
                lines.append([])
            continue

        value = values.get(item)
        if value:
            lines[-1].append(value)

    return [
        " — ".join(parts)
        for parts in lines
        if parts
    ]
