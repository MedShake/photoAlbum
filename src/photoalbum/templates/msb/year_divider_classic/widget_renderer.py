from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter

from photoalbum.rendering.fonts import resolve_font_family
from photoalbum.templates.msb.divider_style import divider_font_family, divider_font_size
from photoalbum.templates.msb.theme import msb_theme_from_pack_settings


class YearDividerClassicWidgetRenderer:
    DEFAULT_TITLE_COLOR = "#d0d0d0"

    def paint(self, *, painter: QPainter, instance, photos, target_rect,
              width: int, height: int, translator, render_service,
              set_waiting_key, font_pixel_size, page_width_mm: float = 210.0,
              page_height_mm: float = 297.0, album_pages=(), composition=None,
              thumbnail_cache=None, pixel_rect=None, template_pack_settings=None) -> None:
        year = ""
        if composition is not None:
            page = getattr(composition, "page", None)
            value = getattr(page, "year", None)
            if value is not None:
                year = str(value)

        theme = msb_theme_from_pack_settings(template_pack_settings or {})
        family = divider_font_family(
            instance.settings, "year_divider", theme.default_font_family
        )
        size = divider_font_size(instance.settings, "year_divider", 72.0)
        font = QFont(resolve_font_family(family, fallback=theme.default_font_family))
        font.setBold(True)
        font.setPixelSize(font_pixel_size(size))
        painter.setFont(font)

        local = instance.settings.get("year_divider", {})
        color = QColor(str(local.get("title_color", self.DEFAULT_TITLE_COLOR))) if isinstance(local, dict) else QColor(self.DEFAULT_TITLE_COLOR)
        if not color.isValid():
            color = QColor(self.DEFAULT_TITLE_COLOR)
        painter.setPen(color)
        painter.drawText(target_rect.adjusted(15, 15, -15, -15), Qt.AlignmentFlag.AlignCenter, year)
