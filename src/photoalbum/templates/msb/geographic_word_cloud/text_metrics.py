from __future__ import annotations

from PySide6.QtGui import (
    QFont,
    QFontMetricsF,
    QGuiApplication,
)

from photoalbum.rendering.fonts import (
    DEFAULT_MONOSPACE_FONT,
    resolve_font_family,
)


_CANONICAL_DPI = 1000.0

# Deterministic fallback for pure composition callers that do
# not own a QGuiApplication. It matches the controlled font's
# measured line spacing closely.
_FALLBACK_LINE_HEIGHT_EM = 1.165


def word_cloud_font(
    font_size_pt: float,
) -> QFont:
    """Return the font used by the geographic word cloud."""
    font = QFont(
        resolve_font_family(
            DEFAULT_MONOSPACE_FONT,
            fallback=DEFAULT_MONOSPACE_FONT,
        )
    )
    font.setBold(True)
    font.setPixelSize(
        max(
            1,
            round(
                font_size_pt
                * _CANONICAL_DPI
                / 72.0
            ),
        )
    )
    return font


def physical_line_height_mm(
    font_size_pt: float,
) -> float:
    """Physical height of one rendered word-cloud line."""
    if QGuiApplication.instance() is None:
        return (
            font_size_pt
            * _FALLBACK_LINE_HEIGHT_EM
            * 25.4
            / 72.0
        )

    metrics = QFontMetricsF(
        word_cloud_font(font_size_pt)
    )

    return (
        metrics.lineSpacing()
        * 25.4
        / _CANONICAL_DPI
    )


def physical_text_width_mm(
    text: str,
    font_size_pt: float,
) -> float:
    """Physical advance width of rendered word-cloud text."""
    if QGuiApplication.instance() is None:
        # The controlled font is monospace and its measured
        # advance is approximately 0.602 em per character.
        return (
            len(text)
            * font_size_pt
            * 0.602
            * 25.4
            / 72.0
        )

    metrics = QFontMetricsF(
        word_cloud_font(font_size_pt)
    )

    return (
        metrics.horizontalAdvance(text)
        * 25.4
        / _CANONICAL_DPI
    )
