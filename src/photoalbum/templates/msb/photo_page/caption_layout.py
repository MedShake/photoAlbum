from __future__ import annotations

from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication

from photoalbum.i18n.date_formatter import format_datetime
from photoalbum.album.composition import PhotoCaptionContent
from .caption_style import caption_font_family, caption_font_size, caption_lines

_CANONICAL_DPI = 1000.0

def _font(settings: dict) -> QFont:
    font = QFont(caption_font_family(settings))
    font.setBold(False)
    font.setPixelSize(max(1, round(caption_font_size(settings) * _CANONICAL_DPI / 72.0)))
    return font

def _width_px(width_mm: float) -> float:
    return max(1.0, width_mm * _CANONICAL_DPI / 25.4)

def physical_line_height_mm(
    settings: dict,
) -> float:
    """Physical height of one rendered caption line."""

    if QGuiApplication.instance() is None:
        # Keep pure/non-GUI composition usable.
        return 4.0

    metrics = QFontMetricsF(
        _font(settings)
    )

    return max(
        0.1,
        metrics.lineSpacing()
        * 25.4
        / _CANONICAL_DPI,
    )


def wrap_text(text: str, *, width_mm: float, settings: dict) -> list[str]:
    metrics = QFontMetricsF(_font(settings))
    limit = _width_px(width_mm)
    result: list[str] = []

    def split_long(token: str) -> list[str]:
        chunks: list[str] = []
        rest = token
        while rest and metrics.horizontalAdvance(rest) > limit:
            lo, hi = 1, len(rest)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if metrics.horizontalAdvance(rest[:mid]) <= limit:
                    lo = mid
                else:
                    hi = mid - 1
            cut = max(1, lo)
            chunks.append(rest[:cut])
            rest = rest[cut:]
        if rest:
            chunks.append(rest)
        return chunks

    for logical in text.splitlines() or [text]:
        words = logical.split()
        if not words:
            result.append("")
            continue
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if metrics.horizontalAdvance(candidate) <= limit:
                current = candidate
                continue
            if current:
                result.append(current)
                current = ""
            pieces = split_long(word)
            if len(pieces) > 1:
                result.extend(pieces[:-1])
            current = pieces[-1]
        if current:
            result.append(current)
    return result

def display_lines(content: PhotoCaptionContent, *, width_mm: float, settings: dict) -> list[str]:
    logical = caption_lines(
        caption_text=content.caption_text,
        capture_datetime_text=(format_datetime(content.capture_datetime) if content.capture_datetime is not None else None),
        location_text=content.location_text,
        settings=settings,
    )
    result: list[str] = []
    for line in logical:
        result.extend(wrap_text(line, width_mm=width_mm, settings=settings))
    return result

def required_line_count(
    content: PhotoCaptionContent,
    *,
    width_mm: float,
    settings: dict,
) -> int:
    # Pure composition tests and third-party non-Qt callers may run
    # without a GUI application. The real preview and PDF paths both
    # own one; only those paths can ask Qt for canonical font metrics.
    if QGuiApplication.instance() is None:
        return content.line_count
    return len(
        display_lines(
            content,
            width_mm=width_mm,
            settings=settings,
        )
    )
