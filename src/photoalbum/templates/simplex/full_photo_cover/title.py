from __future__ import annotations

from math import isfinite
from typing import Callable, Iterable

from photoalbum.rendering.fonts import resolve_font_family


DEFAULT_TITLE_COLOR = "#d0d0d0"

TITLE_POSITIONS = (
    "very_high",
    "high",
    "upper_middle",
    "center",
    "lower_middle",
    "low",
    "very_low",
)


def title_settings(settings: dict) -> dict:
    value = settings.get("title", {})
    return value if isinstance(value, dict) else {}


def title_visible(settings: dict) -> bool:
    return bool(title_settings(settings).get("visible", True))


def title_mode(settings: dict) -> str:
    value = str(
        title_settings(settings).get(
            "mode",
            "automatic",
        )
    )
    return (
        value
        if value in {"automatic", "custom"}
        else "automatic"
    )


def custom_title_text(settings: dict) -> str:
    return str(
        title_settings(settings).get(
            "text",
            "",
        )
    )


def title_position(settings: dict) -> str:
    value = str(
        title_settings(settings).get(
            "position",
            "center",
        )
    )
    return (
        value
        if value in TITLE_POSITIONS
        else "center"
    )


def title_position_index(settings: dict) -> int:
    return TITLE_POSITIONS.index(
        title_position(settings)
    )


def title_color(settings: dict) -> str:
    from PySide6.QtGui import QColor

    value = str(
        title_settings(settings).get(
            "color",
            DEFAULT_TITLE_COLOR,
        )
    )
    return (
        value
        if QColor(value).isValid()
        else DEFAULT_TITLE_COLOR
    )


def title_font_family(settings: dict) -> str:
    value = title_settings(settings).get(
        "font_family"
    )
    requested = (
        str(value)
        if value is not None
        else None
    )
    return resolve_font_family(requested)


def default_title_font_size(title: str) -> float:
    title = title.strip()

    if len(title) == 4 and title.isdigit():
        return 72.0

    if (
        len(title) == 9
        and title[4] in ("-", "–")
        and title[:4].isdigit()
        and title[5:].isdigit()
    ):
        return 52.0

    return 44.0


def title_font_size(
    settings: dict,
    title: str,
) -> float:
    default = default_title_font_size(title)

    try:
        value = float(
            title_settings(settings).get(
                "font_size",
                default,
            )
        )
    except (TypeError, ValueError):
        return default

    return (
        value
        if isfinite(value)
        and 1 <= value <= 300
        else default
    )


def automatic_title(
    photos: Iterable,
    month_name: Callable[[int], str],
) -> str:
    dates = sorted(
        photo.capture_datetime
        for photo in photos
        if getattr(
            photo,
            "capture_datetime",
            None,
        ) is not None
    )

    if not dates:
        return ""

    first = dates[0]
    last = dates[-1]

    if (
        first.year == last.year
        and first.month == last.month
    ):
        month = month_name(first.month)

        if month:
            month = (
                month[:1].upper()
                + month[1:]
            )

        return f"{month} {first.year}"

    if first.year == last.year:
        return str(first.year)

    return f"{first.year}–{last.year}"


def effective_title(
    settings: dict,
    photos: Iterable,
    month_name: Callable[[int], str],
) -> str:
    if title_mode(settings) == "custom":
        return custom_title_text(settings)

    return automatic_title(
        photos,
        month_name,
    )
