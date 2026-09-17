from __future__ import annotations

from dataclasses import dataclass, field

from photoalbum.rendering.fonts import (
    DEFAULT_SANS_FONT,
)


Color = tuple[int, int, int]


DEFAULT_MONTH_COLORS: dict[int, Color] = {
    1: (72, 155, 207),
    2: (134, 96, 188),
    3: (76, 168, 108),
    4: (144, 198, 101),
    5: (238, 201, 88),
    6: (242, 162, 91),
    7: (228, 104, 71),
    8: (200, 76, 76),
    9: (210, 108, 162),
    10: (186, 94, 186),
    11: (90, 125, 206),
    12: (88, 185, 174),
}


def default_month_colors() -> dict[int, Color]:
    """Return an independent copy of the MSB month palette."""
    return dict(DEFAULT_MONTH_COLORS)


def _valid_color(value: object) -> Color | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None

    try:
        color = tuple(int(component) for component in value)
    except (TypeError, ValueError):
        return None

    if not all(0 <= component <= 255 for component in color):
        return None

    return color


@dataclass(frozen=True)
class MsbTheme:
    """
    Project-persisted visual theme for the MSB template pack.

    Values are deliberately materialized in the project rather than
    dynamically inherited from application defaults. An existing project
    therefore keeps the same appearance if future Photo Album releases
    change the built-in MSB defaults.
    """

    month_colors: dict[int, Color] = field(
        default_factory=default_month_colors
    )
    default_font_family: str = DEFAULT_SANS_FONT

    def color_for_month(self, month: int) -> Color:
        return self.month_colors.get(
            month,
            DEFAULT_MONTH_COLORS.get(month, (0, 0, 0)),
        )

    def to_data(self) -> dict[str, object]:
        return {
            "month_colors": {
                str(month): list(self.color_for_month(month))
                for month in range(1, 13)
            },
            "default_font_family": self.default_font_family,
        }

    @classmethod
    def from_data(cls, data: object) -> "MsbTheme":
        if not isinstance(data, dict):
            return cls()

        raw_colors = data.get("month_colors", {})
        colors = default_month_colors()

        if isinstance(raw_colors, dict):
            for month in range(1, 13):
                value = raw_colors.get(str(month))
                if value is None:
                    value = raw_colors.get(month)

                color = _valid_color(value)
                if color is not None:
                    colors[month] = color

        requested_font = data.get(
            "default_font_family",
            DEFAULT_SANS_FONT,
        )

        # Theme deserialization is deliberately Qt-independent.
        # Font availability is a rendering/UI concern: resolving it
        # here would require a QGuiApplication and makes the persisted
        # project model unusable in headless contexts and unit tests.
        if not isinstance(requested_font, str):
            requested_font = DEFAULT_SANS_FONT

        requested_font = requested_font.strip()
        if not requested_font:
            requested_font = DEFAULT_SANS_FONT

        return cls(
            month_colors=colors,
            default_font_family=requested_font,
        )


def msb_theme_from_pack_settings(
    pack_settings: object,
) -> MsbTheme:
    """
    Extract the MSB theme from AlbumStructureSettings.template_pack_settings.
    """
    if not isinstance(pack_settings, dict):
        return MsbTheme()

    msb = pack_settings.get("msb", {})
    if not isinstance(msb, dict):
        return MsbTheme()

    return MsbTheme.from_data(
        msb.get("theme", {})
    )


def pack_settings_with_msb_theme(
    pack_settings: object,
    theme: MsbTheme,
) -> dict[str, object]:
    """
    Return a copy of pack settings containing the complete MSB theme.
    """
    result = (
        dict(pack_settings)
        if isinstance(pack_settings, dict)
        else {}
    )

    msb = result.get("msb", {})
    msb = dict(msb) if isinstance(msb, dict) else {}

    msb["theme"] = theme.to_data()
    result["msb"] = msb

    return result


def palette_to_settings(
    colors: dict[int, Color],
) -> list[list[int]]:
    """JSON-compatible ordered palette."""
    return [
        list(colors[month])
        for month in range(1, 13)
    ]


def palette_from_settings(
    value: object,
    *,
    fallback: dict[int, Color] | None = None,
) -> dict[int, Color]:
    """
    Decode a local template palette.

    Invalid/missing entries fall back to the supplied palette, or to
    the built-in MSB palette.
    """
    result = dict(
        fallback
        if fallback is not None
        else DEFAULT_MONTH_COLORS
    )

    if not isinstance(value, (list, tuple)):
        return result

    for index, raw in enumerate(value[:12], start=1):
        color = _valid_color(raw)
        if color is not None:
            result[index] = color

    return result
