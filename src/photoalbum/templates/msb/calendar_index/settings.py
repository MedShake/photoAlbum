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
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.templates.msb.calendar_index.composition import (
    available_calendar_years,
    compose_calendar_index,
)
from photoalbum.templates.msb.calendar_index.painter import (
    paint_calendar_index,
)
from photoalbum.templates.msb.theme import (
    msb_theme_from_pack_settings,
)

from photoalbum.templates.msb.settings_base import (
    MsbTemplateSettingsWidget,
)


class CalendarIndexSettingsWidget(
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
        left_layout.setSpacing(12)

        left_layout.addWidget(
            self.create_page_settings_title()
        )

        form = QFormLayout()

        self._year_combo = QComboBox()

        form.addRow(
            self._translator.tr(
                "calendar_index.year"
            ),
            self._year_combo,
        )

        left_layout.addLayout(form)
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

    def _load_state(
        self,
    ) -> None:
        years = available_calendar_years(
            self._photos
        )

        settings = self._instance.settings.get(
            "calendar_index",
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

        self._year_combo.blockSignals(
            True
        )

        self._year_combo.clear()

        for year in years:
            self._year_combo.addItem(
                str(year),
                year,
            )

        if years:
            if selected_year not in years:
                selected_year = years[0]

            index = self._year_combo.findData(
                selected_year
            )

            self._year_combo.setCurrentIndex(
                max(
                    index,
                    0,
                )
            )

            # Persist even the automatically selected year.
            self._save_year(
                selected_year,
                emit=False,
            )

        self._year_combo.blockSignals(
            False
        )

        self._year_combo.currentIndexChanged.connect(
            self._year_changed
        )

    def _save_year(
        self,
        year,
        *,
        emit: bool = True,
    ) -> None:
        settings = dict(
            self._instance.settings
        )

        calendar_settings = dict(
            settings.get(
                "calendar_index",
                {},
            )
        )

        calendar_settings[
            "year"
        ] = year

        settings[
            "calendar_index"
        ] = calendar_settings

        self._instance = replace(
            self._instance,
            settings=settings,
        )

        if emit:
            self.instance_changed.emit()

    def _year_changed(
        self,
        index: int,
    ) -> None:
        year = self._year_combo.itemData(
            index
        )

        self._save_year(
            year
        )

        self._render_preview()

    def _render_preview(
        self,
    ) -> None:
        year = self._year_combo.currentData()

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

        if year is None:
            painter.setPen(
                Qt.GlobalColor.darkGray
            )

            painter.drawText(
                pixmap.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._translator.tr(
                    "calendar_index.no_year"
                ),
            )
        else:
            # In the settings dialog there is intentionally no
            # pagination context yet, so Page N is omitted.
            theme = msb_theme_from_pack_settings(
                self._template_pack_settings
            )

            composition = compose_calendar_index(
                self._photos,
                year=year,
                month_colors=theme.month_colors,
            )

            paint_calendar_index(
                painter,
                target_rect=pixmap.rect(),
                composition=composition,
                translator=self._translator,
                page_width_mm=self._page_format.width_mm,
                page_height_mm=self._page_format.height_mm,
            )

        painter.end()

        self._preview_label.setPixmap(
            pixmap
        )
