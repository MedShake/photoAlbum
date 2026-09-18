from __future__ import annotations

from dataclasses import replace
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QVBoxLayout, QWidget
from photoalbum.album import A4, PageFormat, PageInstance
from photoalbum.album.planning import PlanItemKind
from photoalbum.rendering.fonts import available_photo_album_fonts
from photoalbum.templates.msb.divider_style import divider_font_family, divider_font_size
from photoalbum.templates.msb.settings_base import MsbTemplateSettingsWidget
from photoalbum.templates.msb.theme import msb_theme_from_pack_settings

class MonthDividerSimpleSettingsWidget(MsbTemplateSettingsWidget):
    PREVIEW_WIDTH=420; PREVIEW_HEIGHT=594
    def __init__(self,instance:PageInstance,photos,*,translator,render_service=None,page_format:PageFormat=A4,template_pack_settings=None,parent=None)->None:
        super().__init__(instance,photos,translator=translator,render_service=render_service,page_format=page_format,template_pack_settings=template_pack_settings,parent=parent); self._create_content(); self._load_state(); self._connect_change_signals(); self._render_preview()
    def _create_content(self):
        root=QHBoxLayout(self); root.setSpacing(28); left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(12); ll.addWidget(self.create_page_settings_title()); form=QFormLayout(); self._font=QComboBox()
        for family in available_photo_album_fonts(): self._font.addItem(family,family)
        self._size=QDoubleSpinBox(); self._size.setRange(1,300); self._size.setDecimals(1); self._size.setSuffix(" pt"); form.addRow(self._translator.tr("page_settings.title_font_family"),self._font); form.addRow(self._translator.tr("page_settings.title_font_size"),self._size); ll.addLayout(form); ll.addSpacing(12); ll.addWidget(self.create_msb_theme_group())
        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8); rl.addWidget(self.create_preview_title()); self._preview=self.create_preview_label(self.PREVIEW_WIDTH,self.PREVIEW_HEIGHT); rl.addWidget(self._preview,alignment=Qt.AlignmentFlag.AlignTop); root.addWidget(left,1); root.addWidget(right,0)
    def _connect_change_signals(self):
        self._font.currentIndexChanged.connect(self._changed)
        self._size.valueChanged.connect(self._changed)

    def _load_state(self):
        theme=msb_theme_from_pack_settings(self._template_pack_settings); family=divider_font_family(self._instance.settings,"month_divider_simple",theme.default_font_family); i=self._font.findData(family)
        if i>=0:self._font.setCurrentIndex(i)
        self._size.setValue(divider_font_size(self._instance.settings,"month_divider_simple",72.0))
    def _changed(self,*args):
        settings=dict(self._instance.settings); local=dict(settings.get("month_divider_simple",{})); local["title_font_family"]=self._font.currentData(); local["title_font_size"]=self._size.value(); settings["month_divider_simple"]=local; self._instance=replace(self._instance,settings=settings); self.instance_changed.emit(); self._render_preview()
    def _render_preview(self):
        self._preview.setPixmap(
            self.render_template_preview(
                width=self.PREVIEW_WIDTH, height=self.PREVIEW_HEIGHT, photos=(),
                kind=PlanItemKind.MONTH_DIVIDER,
                page_attributes={"year": 2025, "month": 6, "cities": ()},
            )
        )

    def msb_theme_changed(self): self._render_preview()
