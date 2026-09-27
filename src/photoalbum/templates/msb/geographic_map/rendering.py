"""Shared rendering options and empty-state painting for preview and export."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from photoalbum.templates.msb.theme import msb_theme_from_pack_settings
from . import defaults
from .painter import paint_geographic_map


def render_options(settings, translator, template_pack_settings=None):
    theme = msb_theme_from_pack_settings(template_pack_settings or {})
    options = {
        key: settings.get(key, getattr(defaults, "DEFAULT_" + key.upper()))
        for key in ("projection", "point_color_mode", "point_size", "point_opacity")
    }
    for key in ("land_color", "water_color", "border_color"):
        options[key] = QColor(settings.get(key, getattr(defaults, "DEFAULT_" + key.upper())))
    options.update(
        marker_color=QColor(settings.get("point_color", defaults.DEFAULT_POINT_COLOR)),
        month_colors={month: QColor(*theme.color_for_month(month)) for month in range(1, 13)},
        show_month_legend=bool(settings.get("show_month_legend", True)),
        month_labels={month: translator.month_name(month) for month in range(1, 13)},
        empty_message=translator.tr("page_settings.map_no_geographic_data"),
    )
    return options


def paint_map(painter, rect, composition, *, empty_message, **options):
    painter.save()
    try:
        paint_geographic_map(painter, rect, composition, **options)
        if not composition.markers:
            painter.setPen(Qt.GlobalColor.darkGray)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, empty_message)
    finally:
        painter.restore()
