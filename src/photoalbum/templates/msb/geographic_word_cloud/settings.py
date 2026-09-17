from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.rendering.page_geometry import (
    PageRenderGeometry,
)
from photoalbum.templates.msb.geographic_word_cloud.composition import (
    compose_geographic_word_cloud,
)
from .painter import (
    paint_geographic_word_cloud,
)

from photoalbum.templates.msb.theme import (
    msb_theme_from_pack_settings,
    palette_from_settings,
    palette_to_settings,
)

from photoalbum.templates.msb.settings_base import (
    MsbTemplateSettingsWidget,
)


class GeographicWordCloudSettingsWidget(
    MsbTemplateSettingsWidget
):
    PREVIEW_WIDTH = 420
    PREVIEW_HEIGHT = 594

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
        self._render_preview()

    def _create_content(
        self,
    ) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(28)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        left_layout.addWidget(
            self.create_page_settings_title()
        )

        form = QFormLayout()

        self._year_combo = QComboBox()

        form.addRow(
            self._translator.tr(
                "page_settings.geographic_photos"
            ),
            self._year_combo,
        )

        left_layout.addLayout(form)

        palette_explanation = QLabel(
            self._translator.tr(
                "page_settings.word_cloud_palette_explanation"
            )
        )
        palette_explanation.setWordWrap(True)
        left_layout.addWidget(palette_explanation)

        self._color_buttons = {}

        palette_grid = QGridLayout()
        palette_grid.setHorizontalSpacing(12)
        palette_grid.setVerticalSpacing(6)

        for month in range(1, 13):
            button = QPushButton()
            button.setFixedWidth(86)

            button.clicked.connect(
                lambda checked=False, m=month:
                    self._choose_palette_color(m)
            )

            self._color_buttons[month] = button

            column = 0 if month <= 6 else 2
            row = (month - 1) % 6

            palette_grid.addWidget(
                QLabel(
                    self._translator.month_name(month)
                ),
                row,
                column,
            )
            palette_grid.addWidget(
                button,
                row,
                column + 1,
            )

        left_layout.addLayout(palette_grid)

        self._restore_theme_palette_button = QPushButton(
            self._translator.tr(
                "page_settings.word_cloud_restore_theme"
            )
        )
        self._restore_theme_palette_button.clicked.connect(
            self._restore_theme_palette
        )
        left_layout.addWidget(
            self._restore_theme_palette_button
        )

        left_layout.addSpacing(12)
        left_layout.addWidget(
            self.create_msb_theme_group()
        )

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_layout.addWidget(
            self.create_preview_title()
        )

        self._preview_label = QLabel()
        self._update_preview_size()

        self._preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self._preview_label.setStyleSheet(
            "border: 1px solid #888;"
            "background: white;"
        )

        right_layout.addWidget(
            self._preview_label,
            alignment=Qt.AlignmentFlag.AlignTop,
        )

        root.addWidget(left, 1)
        root.addWidget(right, 0)

    def msb_theme_changed(
        self,
    ) -> None:
        self._render_preview()

    def _update_preview_size(
        self,
    ) -> None:
        width = self.PREVIEW_WIDTH

        height = round(
            width
            * self._page_format.height_mm
            / self._page_format.width_mm
        )

        self._preview_label.setFixedSize(
            width,
            height,
        )

    def _load_state(
        self,
    ) -> None:
        self._year_combo.blockSignals(
            True
        )

        self._year_combo.clear()

        self._year_combo.addItem(
            self._translator.tr(
                "page_settings.all_photos"
            ),
            None,
        )

        years = sorted(
            {
                photo.capture_datetime.year
                for photo in self._photos
                if (
                    photo.capture_datetime
                    is not None
                )
            }
        )

        for year in years:
            self._year_combo.addItem(
                str(year),
                year,
            )

        settings = self._instance.settings.get(
            "geographic_word_cloud",
            {},
        )

        if not isinstance(
            settings,
            dict,
        ):
            settings = {}

        theme = msb_theme_from_pack_settings(
            self._template_pack_settings
        )

        self._theme_palette = dict(
            theme.month_colors
        )

        self._has_local_palette = (
            "palette" in settings
        )

        self._palette = palette_from_settings(
            settings.get("palette"),
            fallback=self._theme_palette,
        )

        self._update_palette_buttons()

        selected_year = settings.get(
            "year"
        )

        index = self._year_combo.findData(
            selected_year
        )

        if index < 0:
            index = 0

        self._year_combo.setCurrentIndex(
            index
        )

        self._year_combo.blockSignals(
            False
        )

        self._year_combo.currentIndexChanged.connect(
            self._scope_changed
        )

    def _update_palette_buttons(
        self,
    ) -> None:
        for month, button in self._color_buttons.items():
            rgb = self._palette[month]
            color_text = "#{:02X}{:02X}{:02X}".format(
                *rgb
            )

            button.setText(color_text)
            button.setStyleSheet(
                "QPushButton {"
                f"background-color: {color_text};"
                "}"
            )

        self._restore_theme_palette_button.setEnabled(
            self._has_local_palette
        )

    def _store_local_palette(
        self,
    ) -> None:
        settings = dict(
            self._instance.settings
        )

        geo_settings = dict(
            settings.get(
                "geographic_word_cloud",
                {},
            )
        )

        geo_settings["palette"] = palette_to_settings(
            self._palette
        )

        settings["geographic_word_cloud"] = (
            geo_settings
        )

        self._instance = replace(
            self._instance,
            settings=settings,
        )

        self._has_local_palette = True
        self.instance_changed.emit()

    def _choose_palette_color(
        self,
        month: int,
    ) -> None:
        current = QColor(
            *self._palette[month]
        )

        color = QColorDialog.getColor(
            current,
            self,
            self._translator.tr(
                "page_settings.word_cloud_choose_color"
            ),
        )

        if not color.isValid():
            return

        self._palette[month] = (
            color.red(),
            color.green(),
            color.blue(),
        )

        self._store_local_palette()
        self._update_palette_buttons()
        self._render_preview()

    def _restore_theme_palette(
        self,
    ) -> None:
        self._palette = dict(
            self._theme_palette
        )

        settings = dict(
            self._instance.settings
        )

        geo_settings = dict(
            settings.get(
                "geographic_word_cloud",
                {},
            )
        )

        geo_settings.pop(
            "palette",
            None,
        )

        settings["geographic_word_cloud"] = (
            geo_settings
        )

        self._instance = replace(
            self._instance,
            settings=settings,
        )

        self._has_local_palette = False

        self._update_palette_buttons()
        self.instance_changed.emit()
        self._render_preview()

    def _scope_changed(
        self,
        index: int,
    ) -> None:
        settings = dict(
            self._instance.settings
        )

        geo_settings = dict(
            settings.get(
                "geographic_word_cloud",
                {},
            )
        )

        geo_settings["year"] = (
            self._year_combo.itemData(
                index
            )
        )

        settings[
            "geographic_word_cloud"
        ] = geo_settings

        self._instance = replace(
            self._instance,
            settings=settings,
        )

        self.instance_changed.emit()

        self._render_preview()

    def _render_preview(
        self,
    ) -> None:
        year = self._year_combo.currentData()

        # The geographic cloud keeps the historical A4
        # composition geometry on every supported page format.
        # Wider formats such as US Letter therefore gain extra
        # horizontal breathing room instead of stretching the
        # cloud layout.
        cloud = compose_geographic_word_cloud(
            list(
                self._photos
            ),
            year=year,
            page_width_mm=A4.width_mm,
            page_height_mm=A4.height_mm,
            palette=tuple(
                self._palette[month]
                for month in range(1, 13)
            ),
        )

        self._update_preview_size()

        pixmap = QPixmap(
            self._preview_label.size()
        )

        pixmap.fill(
            Qt.GlobalColor.white
        )

        painter = QPainter(
            pixmap
        )

        geometry = PageRenderGeometry(
            width=pixmap.width(),
            height=pixmap.height(),
            page_width_mm=self._page_format.width_mm,
            page_height_mm=self._page_format.height_mm,
        )

        paint_geographic_word_cloud(
            painter,
            target_rect=pixmap.rect(),
            cloud=cloud,
            font_pixel_size=geometry.font_pixel_size,
        )

        if not cloud.words:
            painter.setPen(
                Qt.GlobalColor.darkGray
            )

            painter.drawText(
                pixmap.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._translator.tr(
                    "page_settings.no_geographic_data"
                ),
            )

        painter.end()

        self._preview_label.setPixmap(
            pixmap
        )
