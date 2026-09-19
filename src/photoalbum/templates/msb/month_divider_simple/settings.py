from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import A4, PageFormat, PageInstance
from photoalbum.album.planning import PlanItemKind
from photoalbum.rendering.fonts import available_photo_album_fonts
from photoalbum.templates.msb.divider_style import (
    divider_font_family,
    divider_font_size,
)
from photoalbum.templates.msb.settings_base import (
    MsbTemplateSettingsWidget,
)
from photoalbum.templates.msb.theme import (
    msb_theme_from_pack_settings,
)


class MonthDividerSimpleSettingsWidget(
    MsbTemplateSettingsWidget
):
    PREVIEW_WIDTH = 420
    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator,
        render_service=None,
        page_format: PageFormat = A4,
        template_pack_settings=None,
        parent=None,
    ) -> None:
        super().__init__(
            instance,
            photos,
            translator=translator,
            render_service=render_service,
            page_format=page_format,
            template_pack_settings=template_pack_settings,
            parent=parent,
        )

        self._create_content()
        self._load_state()
        self._connect_change_signals()
        self._render_preview()

    def _create_content(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(28)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(
            self.create_page_settings_title()
        )

        form = QFormLayout()

        self._font = QComboBox()
        for family in available_photo_album_fonts():
            self._font.addItem(
                family,
                family,
            )

        self._size = QDoubleSpinBox()
        self._size.setRange(1, 300)
        self._size.setDecimals(1)
        self._size.setSuffix(" pt")

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

        left_layout.addLayout(form)
        left_layout.addSpacing(12)
        left_layout.addWidget(
            self.create_msb_theme_group()
        )

        self._preview = self.create_preview_label(self.PREVIEW_WIDTH)
        self.add_settings_columns(root, left, self._preview)

    def _connect_change_signals(self) -> None:
        self._font.currentIndexChanged.connect(
            self._changed
        )
        self._size.valueChanged.connect(
            self._changed
        )

    def _load_state(self) -> None:
        theme = msb_theme_from_pack_settings(
            self._template_pack_settings
        )

        family = divider_font_family(
            self._instance.settings,
            "month_divider_simple",
            theme.default_font_family,
        )

        index = self._font.findData(family)
        if index >= 0:
            self._font.setCurrentIndex(index)

        self._size.setValue(
            divider_font_size(
                self._instance.settings,
                "month_divider_simple",
                72.0,
            )
        )

    def _changed(self, *args) -> None:
        settings = dict(
            self._instance.settings
        )
        local = dict(
            settings.get(
                "month_divider_simple",
                {},
            )
        )

        local["title_font_family"] = (
            self._font.currentData()
        )
        local["title_font_size"] = (
            self._size.value()
        )

        settings["month_divider_simple"] = local

        self._instance = replace(
            self._instance,
            settings=settings,
        )

        self.instance_changed.emit()
        self._render_preview()

    def _render_preview(self) -> None:
        self._preview.setPixmap(
            self.render_template_preview(
                width=self._preview.width(), height=self._preview.height(),
                photos=(),
                kind=PlanItemKind.MONTH_DIVIDER,
                page_attributes={
                    "year": 2025,
                    "month": 6,
                    "cities": (),
                },
            )
        )

    def msb_theme_changed(self) -> None:
        self._render_preview()
