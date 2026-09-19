from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import PageInstance
from photoalbum.templates.msb.settings_base import (
    MsbTemplateSettingsWidget,
)
from photoalbum.rendering.fonts import (
    DEFAULT_SERIF_FONT,
    available_photo_album_fonts,
    resolve_font_family,
)


class DedicationSettingsWidget(
    MsbTemplateSettingsWidget
):
    DEFAULT_TEXT = ""
    DEFAULT_FRAME_COLOR = "#808080"
    DEFAULT_FRAME_WIDTH = 0.5
    DEFAULT_FONT_FAMILY = DEFAULT_SERIF_FONT
    DEFAULT_FONT_SIZE = 12.0

    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator,
        render_service=None,
        page_format=None,
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

        settings = instance.settings.get(
            "dedication",
            {},
        )

        if not isinstance(settings, dict):
            settings = {}

        self._text = str(
            settings.get(
                "text",
                self.DEFAULT_TEXT,
            )
        )

        self._frame_color = str(
            settings.get(
                "frame_color",
                self.DEFAULT_FRAME_COLOR,
            )
        )

        if not QColor(
            self._frame_color
        ).isValid():
            self._frame_color = (
                self.DEFAULT_FRAME_COLOR
            )

        try:
            self._frame_width = float(
                settings.get(
                    "frame_width",
                    self.DEFAULT_FRAME_WIDTH,
                )
            )
        except (TypeError, ValueError):
            self._frame_width = (
                self.DEFAULT_FRAME_WIDTH
            )

        self._font_family = resolve_font_family(
            str(
                settings.get(
                    "font_family",
                    self.DEFAULT_FONT_FAMILY,
                )
            ),
            fallback=self.DEFAULT_FONT_FAMILY,
        )

        try:
            self._font_size = float(
                settings.get(
                    "font_size",
                    self.DEFAULT_FONT_SIZE,
                )
            )
        except (TypeError, ValueError):
            self._font_size = (
                self.DEFAULT_FONT_SIZE
            )

        self._font_size = max(
            6.0,
            min(72.0, self._font_size),
        )

        self._create_content()

    PREVIEW_WIDTH = 360
    def _create_content(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(24)

        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(
            self.create_page_settings_title()
        )

        layout.addWidget(
            QLabel(
                "Texte de la dédicace (Markdown)"
            )
        )

        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(
            self._text
        )
        self._text_edit.setPlaceholderText(
            "**Pour vous**\n\n"
            "Avec toute notre affection."
        )
        self._text_edit.textChanged.connect(
            self._text_changed
        )
        layout.addWidget(
            self._text_edit,
            1,
        )

        form = QFormLayout()

        self._font_combo = QComboBox()
        for family in available_photo_album_fonts():
            self._font_combo.addItem(
                family,
                family,
            )

        font_index = self._font_combo.findData(
            self._font_family
        )
        if font_index >= 0:
            self._font_combo.setCurrentIndex(
                font_index
            )

        self._font_combo.currentIndexChanged.connect(
            self._font_changed
        )
        form.addRow(
            "Police",
            self._font_combo,
        )

        self._font_size_spin = QDoubleSpinBox()
        self._font_size_spin.setRange(6.0, 72.0)
        self._font_size_spin.setDecimals(1)
        self._font_size_spin.setSingleStep(0.5)
        self._font_size_spin.setSuffix(" pt")
        self._font_size_spin.setValue(
            self._font_size
        )
        self._font_size_spin.valueChanged.connect(
            self._font_size_changed
        )
        form.addRow(
            "Taille du texte",
            self._font_size_spin,
        )

        self._frame_color_button = QPushButton()
        self._frame_color_button.clicked.connect(
            self._choose_frame_color
        )
        form.addRow(
            "Couleur du cadre",
            self._frame_color_button,
        )

        self._frame_width_spin = QDoubleSpinBox()
        self._frame_width_spin.setRange(0.1, 10.0)
        self._frame_width_spin.setDecimals(1)
        self._frame_width_spin.setSingleStep(0.1)
        self._frame_width_spin.setSuffix(" pt")
        self._frame_width_spin.setValue(
            self._frame_width
        )
        self._frame_width_spin.valueChanged.connect(
            self._frame_width_changed
        )
        form.addRow(
            "Épaisseur du cadre",
            self._frame_width_spin,
        )

        layout.addLayout(form)
        layout.addSpacing(12)
        layout.addWidget(
            self.create_msb_theme_group()
        )

        self._preview_label = self.create_preview_label(self.PREVIEW_WIDTH)
        self.add_settings_columns(root, left, self._preview_label)

        self._update_frame_color_button()
        self._render_preview()

    def _render_preview(self):
        self._preview_label.setPixmap(
            self.render_template_preview(
                width=self._preview_label.width(), height=self._preview_label.height(), photos=self._photos,
                page_attributes={},
            )
        )

    def msb_theme_changed(self) -> None:
        self._render_preview()

    def _update_frame_color_button(
        self,
    ) -> None:
        self._frame_color_button.setText(
            self._frame_color
        )

    def _save_settings(
        self,
    ) -> None:
        settings = dict(
            self._instance.settings
        )

        settings["dedication"] = {
            "text": self._text,
            "frame_color": self._frame_color,
            "frame_width": self._frame_width,
            "font_family": self._font_family,
            "font_size": self._font_size,
        }

        self._instance = replace(
            self._instance,
            settings=settings,
        )

        self.instance_changed.emit()
        self._render_preview()

    def _text_changed(
        self,
    ) -> None:
        self._text = (
            self._text_edit.toPlainText()
        )

        self._save_settings()

    def _font_changed(
        self,
        index: int,
    ) -> None:
        family = self._font_combo.itemData(
            index
        )

        if not family:
            return

        self._font_family = resolve_font_family(
            str(family),
            fallback=self.DEFAULT_FONT_FAMILY,
        )

        self._save_settings()

    def _font_size_changed(
        self,
        value: float,
    ) -> None:
        self._font_size = float(value)
        self._save_settings()

    def _frame_width_changed(
        self,
        value: float,
    ) -> None:
        self._frame_width = float(value)

        self._save_settings()

    def _choose_frame_color(
        self,
    ) -> None:
        color = QColorDialog.getColor(
            QColor(
                self._frame_color
            ),
            self,
            "Couleur du cadre",
        )

        if not color.isValid():
            return

        self._frame_color = color.name()

        self._update_frame_color_button()
        self._save_settings()
