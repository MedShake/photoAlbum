from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from photoalbum.album import A4, PageFormat, PageInstance
from photoalbum.templates.msb.settings_base import MsbTemplateSettingsWidget
from .widget_renderer import MonthDividerClassicWidgetRenderer


class MonthDividerClassicSettingsWidget(MsbTemplateSettingsWidget):
    PREVIEW_WIDTH=420; PREVIEW_HEIGHT=594
    SAMPLE_CITIES = (
        "Bussy-lès-Daours",
        "Amiens",
        "Rennes",
        "Pléneuf-Val-André",
        "Orvault",
        "Nantes",
        "Saint-Herblain",
    )

    def __init__(self, instance: PageInstance, photos, *, translator, render_service=None,
                 page_format: PageFormat=A4, template_pack_settings=None, parent=None) -> None:
        super().__init__(instance,photos,translator=translator,render_service=render_service,page_format=page_format,template_pack_settings=template_pack_settings,parent=parent)
        root=QHBoxLayout(self); root.setSpacing(28)
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(12)
        ll.addWidget(self.create_page_settings_title()); ll.addWidget(self.create_no_page_settings_label())
        note=QLabel(self._translator.tr("month_divider.sample_cities_note")); note.setWordWrap(True); ll.addWidget(note); ll.addSpacing(12); ll.addWidget(self.create_msb_theme_group())
        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8); rl.addWidget(self.create_preview_title())
        self._preview=QLabel(); self._preview.setFixedSize(self.PREVIEW_WIDTH,self.PREVIEW_HEIGHT); self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self._preview.setStyleSheet("border: 1px solid #888;background: white;")
        rl.addWidget(self._preview,alignment=Qt.AlignmentFlag.AlignTop); root.addWidget(left,1); root.addWidget(right,0); self._render_preview()

    def _render_preview(self):
        pix=QPixmap(self.PREVIEW_WIDTH,self.PREVIEW_HEIGHT); pix.fill(Qt.GlobalColor.white); painter=QPainter(pix)
        page=SimpleNamespace(year=2025,month=6,cities=self.SAMPLE_CITIES); comp=SimpleNamespace(page=page)
        def pixel_rect(r): return QRectF(r.x*pix.width(),r.y*pix.height(),r.width*pix.width(),r.height*pix.height())
        MonthDividerClassicWidgetRenderer().paint(painter=painter,instance=self._instance,photos=(),target_rect=pix.rect(),width=pix.width(),height=pix.height(),translator=self._translator,render_service=None,set_waiting_key=None,font_pixel_size=lambda pt:max(1,round(pt*pix.width()/595)),page_width_mm=self._page_format.width_mm,page_height_mm=self._page_format.height_mm,composition=comp,pixel_rect=pixel_rect,template_pack_settings=self._template_pack_settings)
        painter.end(); self._preview.setPixmap(pix)

    def msb_theme_changed(self): self._render_preview()
