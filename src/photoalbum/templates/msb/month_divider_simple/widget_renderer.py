from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter

from photoalbum.templates.msb.divider_style import divider_font_family, divider_font_size
from photoalbum.templates.msb.theme import msb_theme_from_pack_settings
from photoalbum.templates.msb.simple_divider_titles import divider_title


class MonthDividerSimpleWidgetRenderer:
    def paint(self, *, painter: QPainter, instance, photos, target_rect, width: int, height: int,
              translator, render_service, set_waiting_key, font_pixel_size, page_width_mm: float=210.0,
              page_height_mm: float=297.0, album_pages=(), composition=None, thumbnail_cache=None,
              pixel_rect=None, template_pack_settings=None, temporal_context=(),
        **kwargs,
    ) -> None:
        page=getattr(composition,"page",None) if composition is not None else None
        month=getattr(page,"month",None)
        if month is None: return
        title=divider_title("month", page, instance.settings, translator, temporal_context)
        theme=msb_theme_from_pack_settings(template_pack_settings or {})
        family=divider_font_family(instance.settings,"month_divider_simple",theme.default_font_family)
        size=divider_font_size(instance.settings,"month_divider_simple",72.0)
        font=QFont(family); font.setBold(True); font.setPixelSize(font_pixel_size(size)); painter.setFont(font)
        painter.setPen(QColor(*theme.color_for_month(month)))
        painter.drawText(target_rect.adjusted(15,15,-15,-15),Qt.AlignmentFlag.AlignCenter,title)
