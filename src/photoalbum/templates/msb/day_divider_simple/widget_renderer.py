from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF

from photoalbum.templates.msb.divider_style import divider_font_family, divider_font_size
from photoalbum.templates.msb.theme import msb_theme_from_pack_settings
from photoalbum.templates.msb.simple_divider_titles import divider_title


def day_title(page, translator, settings=None, context=()) -> str:
    return divider_title("day", page, settings or {}, translator, context)


class DayDividerSimpleWidgetRenderer:
    def paint(self, *, painter, instance, photos, target_rect, width, height,
              translator, render_service, set_waiting_key, font_pixel_size,
              page_width_mm=210.0, page_height_mm=297.0, album_pages=(),
              composition=None, thumbnail_cache=None, pixel_rect=None,
              template_pack_settings=None, temporal_context=(), **kwargs) -> None:
        page = getattr(composition, "page", None)
        if page is None or any(getattr(page, part, None) is None for part in ("year", "month", "day")):
            return
        theme = msb_theme_from_pack_settings(template_pack_settings or {})
        family = divider_font_family(instance.settings, "day_divider_simple", theme.default_font_family)
        size = divider_font_size(instance.settings, "day_divider_simple", 48.0)
        title = day_title(page, translator, instance.settings, temporal_context)
        rect = target_rect.adjusted(15, 15, -15, -15)
        font = QFont(family)
        font.setBold(True)
        font.setPixelSize(max(1, font_pixel_size(size)))
        # Keep the full date readable on narrow formats and in either language.
        metrics = QFontMetricsF(font)
        scale = min(1.0, rect.width() / max(1.0, metrics.horizontalAdvance(title)),
                    rect.height() / max(1.0, metrics.height()))
        font.setPixelSize(max(1, int(font.pixelSize() * scale)))
        painter.setFont(font)
        painter.setPen(QColor(*theme.color_for_month(page.month)))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, title)
