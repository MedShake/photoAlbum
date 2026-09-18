from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import A4, PageFormat, PageInstance
from photoalbum.album.planning import PlanItemKind
from photoalbum.rendering.fonts import available_photo_album_fonts, resolve_font_family
from photoalbum.templates.msb.divider_style import divider_font_family, divider_font_size
from photoalbum.templates.msb.settings_base import MsbTemplateSettingsWidget
from photoalbum.templates.msb.theme import msb_theme_from_pack_settings


class YearDividerClassicSettingsWidget(MsbTemplateSettingsWidget):
    DEFAULT_TITLE_COLOR = "#d0d0d0"
    PREVIEW_WIDTH = 420
    PREVIEW_HEIGHT = 594

    def __init__(self, instance: PageInstance, photos, *, translator, render_service=None,
                 page_format: PageFormat = A4, template_pack_settings=None, parent=None) -> None:
        super().__init__(instance, photos, translator=translator, render_service=render_service,
                         page_format=page_format, template_pack_settings=template_pack_settings, parent=parent)
        self._create_content()
        self._load_state()
        self._connect_change_signals()
        self._render_preview()

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
        self._preview=self.create_preview_label(self.PREVIEW_WIDTH,self.PREVIEW_HEIGHT)
        rl.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignTop); root.addWidget(left,1); root.addWidget(right,0)
    def _connect_change_signals(self):
        self._font.currentIndexChanged.connect(self._changed)
        self._size.valueChanged.connect(self._changed)

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
                    self.DEFAULT_TITLE_COLOR,
                )
            )
            if isinstance(local, dict)
            else self.DEFAULT_TITLE_COLOR
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
        self._preview.setPixmap(
            self.render_template_preview(
                width=self.PREVIEW_WIDTH, height=self.PREVIEW_HEIGHT, photos=(),
                kind=PlanItemKind.YEAR_DIVIDER,
                page_attributes={"year": 2025},
            )
        )

    def msb_theme_changed(self): self._render_preview()
