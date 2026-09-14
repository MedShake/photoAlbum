from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from photoalbum.album import PageInstance
from photoalbum.album.geographic_word_cloud import (
    compose_geographic_word_cloud,
)
from photoalbum.gui.geographic_word_cloud_painter import (
    paint_geographic_word_cloud,
)

from .base import PageTemplateSettingsWidget


class GeographicWordCloudSettingsWidget(
    PageTemplateSettingsWidget
):
    PREVIEW_WIDTH = 420
    PREVIEW_HEIGHT = 594

    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator,
        parent=None,
    ) -> None:
        super().__init__(
            instance,
            photos,
            translator=translator,
            parent=parent,
        )

        self._create_content()
        self._load_state()
        self._render_preview()

    def _create_content(
        self,
    ) -> None:
        layout = QVBoxLayout(
            self
        )

        form = QFormLayout()

        self._year_combo = QComboBox()

        form.addRow(
            self._translator.tr(
                "page_settings.geographic_photos"
            ),
            self._year_combo,
        )

        layout.addLayout(
            form
        )

        self._preview_label = QLabel()

        self._preview_label.setFixedSize(
            self.PREVIEW_WIDTH,
            self.PREVIEW_HEIGHT,
        )

        self._preview_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._preview_label.setStyleSheet(
            "border: 1px solid #888;"
            "background: white;"
        )

        layout.addWidget(
            self._preview_label,
            alignment=(
                Qt.AlignmentFlag.AlignCenter
            ),
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

        cloud = compose_geographic_word_cloud(
            list(
                self._photos
            ),
            year=year,
            page_width_mm=210.0,
            page_height_mm=297.0,
        )

        pixmap = QPixmap(
            self.PREVIEW_WIDTH,
            self.PREVIEW_HEIGHT,
        )

        pixmap.fill(
            Qt.GlobalColor.white
        )

        painter = QPainter(
            pixmap
        )

        paint_geographic_word_cloud(
            painter,
            target_rect=pixmap.rect(),
            cloud=cloud,
            page_width_mm=210.0,
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
