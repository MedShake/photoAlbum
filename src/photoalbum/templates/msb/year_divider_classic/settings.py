from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import A4, PageFormat, PageInstance
from photoalbum.rendering.fonts import available_photo_album_fonts, resolve_font_family
from photoalbum.templates.msb.divider_style import divider_font_family, divider_font_size
from photoalbum.templates.msb.settings_base import MsbTemplateSettingsWidget
from photoalbum.templates.msb.theme import msb_theme_from_pack_settings
from .widget_renderer import YearDividerClassicWidgetRenderer


class YearDividerClassicSettingsWidget(MsbTemplateSettingsWidget):
    PREVIEW_WIDTH = 420
    PREVIEW_HEIGHT = 594

    def __init__(self, instance: PageInstance, photos, *, translator, render_service=None,
                 page_format: PageFormat = A4, template_pack_settings=None, parent=None) -> None:
        super().__init__(instance, photos, translator=translator, render_service=render_service,
                         page_format=page_format, template_pack_settings=template_pack_settings, parent=parent)
        self._create_content(); self._load_state(); self._render_preview()

    def _create_content(self):
        root=QHBoxLayout(self); root.setSpacing(28)
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(12)
        ll.addWidget(self.create_page_settings_title())
        form=QFormLayout(); self._font=QComboBox()
        for family in available_photo_album_fonts(): self._font.addItem(family, family)
        self._size=QDoubleSpinBox(); self._size.setRange(1,300); self._size.setDecimals(1); self._size.setSuffix(" pt")
        form.addRow(
            self._translator.tr(
                "page_settings.title_font_family"
            ),
            self._font,
        )
        form.addRow(
            self._translator.tr(
                "page_settings.title_font_size"
            ),
            self._size,
        )

        self._color_button = QPushButton()
        self._color_button.clicked.connect(
            self._choose_title_color
        )

        form.addRow(
            self._translator.tr(
                "page_settings.title_color"
            ),
            self._color_button,
        )

        ll.addLayout(form)
        ll.addSpacing(12)
        ll.addWidget(self.create_msb_theme_group())
        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8); rl.addWidget(self.create_preview_title())
        self._preview=QLabel(); self._preview.setFixedSize(self.PREVIEW_WIDTH,self.PREVIEW_HEIGHT); self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self._preview.setStyleSheet("border: 1px solid #888;background: white;")
        rl.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignTop); root.addWidget(left,1); root.addWidget(right,0)
        self._font.currentIndexChanged.connect(self._changed); self._size.valueChanged.connect(self._changed)

    def _load_state(self):
        theme=msb_theme_from_pack_settings(self._template_pack_settings)
        family=divider_font_family(self._instance.settings,"year_divider",theme.default_font_family)
        i=self._font.findData(family)
        if i>=0: self._font.setCurrentIndex(i)
        self._size.setValue(
            divider_font_size(
                self._instance.settings,
                "year_divider",
                72.0,
            )
        )

        local = self._instance.settings.get(
            "year_divider",
            {},
        )
        self._title_color = (
            str(
                local.get(
                    "title_color",
                    YearDividerClassicWidgetRenderer.DEFAULT_TITLE_COLOR,
                )
            )
            if isinstance(local, dict)
            else YearDividerClassicWidgetRenderer.DEFAULT_TITLE_COLOR
        )
        self._update_color_button()

    def _changed(self, *args):
        settings = dict(self._instance.settings)
        local = dict(
            settings.get(
                "year_divider",
                {},
            )
        )
        local["title_font_family"] = (
            self._font.currentData()
        )
        local["title_font_size"] = (
            self._size.value()
        )
        local["title_color"] = self._title_color

        settings["year_divider"] = local

        self._instance = replace(
            self._instance,
            settings=settings,
        )
        self.instance_changed.emit()
        self._render_preview()

    def _choose_title_color(self):
        color = QColorDialog.getColor(
            QColor(self._title_color),
            self,
            self._translator.tr(
                "page_settings.choose_title_color"
            ),
        )

        if not color.isValid():
            return

        self._title_color = color.name()
        self._update_color_button()
        self._changed()

    def _update_color_button(self):
        self._color_button.setText(
            self._title_color.upper()
        )
        self._color_button.setStyleSheet(
            "QPushButton {"
            f"background-color: {self._title_color};"
            "}"
        )

    def _render_preview(self):
        pix=QPixmap(self.PREVIEW_WIDTH,self.PREVIEW_HEIGHT); pix.fill(Qt.GlobalColor.white); painter=QPainter(pix)
        comp=SimpleNamespace(page=SimpleNamespace(year=2025))
        YearDividerClassicWidgetRenderer().paint(painter=painter,instance=self._instance,photos=(),target_rect=pix.rect(),width=pix.width(),height=pix.height(),translator=self._translator,render_service=None,set_waiting_key=None,font_pixel_size=lambda pt:max(1,round(pt*pix.width()/595)),composition=comp,template_pack_settings=self._template_pack_settings)
        painter.end(); self._preview.setPixmap(pix)

    def msb_theme_changed(self): self._render_preview()
