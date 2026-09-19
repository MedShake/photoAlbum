from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
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
    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator,
        render_service=None,
        page_format: PageFormat = A4,
        template_pack_settings=None,
        usage: str | None = None,
        parent=None,
    ) -> None:
        self._usage = usage

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
            self._translator.tr("calendar_index.year"),
            self._year_combo,
        )

        self._show_title_checkbox = QCheckBox(
            self._translator.tr("calendar_index.show_title")
        )
        self._show_title_checkbox.toggled.connect(
            self._show_title_changed
        )
        form.addRow("", self._show_title_checkbox)

        left_layout.addLayout(form)
        left_layout.addSpacing(12)
        left_layout.addWidget(
            self.create_msb_theme_group()
        )

        self._preview_label = self.create_preview_label(self.PREVIEW_WIDTH)
        self.add_settings_columns(root, left, self._preview_label)

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

        selected_year = settings.get("year")
        self._show_title_checkbox.blockSignals(True)
        self._show_title_checkbox.setChecked(
            bool(settings.get("show_title", True))
        )
        self._show_title_checkbox.blockSignals(False)

        self._year_combo.blockSignals(
            True
        )

        self._year_combo.clear()

        if self._usage == "year_divider":
            self._year_combo.addItem(
                self._translator.tr("calendar_index.year_automatic"),
                None,
            )
            self._year_combo.setEnabled(False)

            self._year_combo.blockSignals(
                False
            )

            self._year_combo.currentIndexChanged.connect(
                self._year_changed
            )
            return

        self._year_combo.setEnabled(True)

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

    def _show_title_changed(self, checked: bool) -> None:
        settings = dict(self._instance.settings)
        calendar_settings = dict(settings.get("calendar_index", {}))
        calendar_settings["show_title"] = bool(checked)
        settings["calendar_index"] = calendar_settings
        self._instance = replace(self._instance, settings=settings)
        self.instance_changed.emit()
        self._render_preview()

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

    def _render_preview(self) -> None:
        year = self._year_combo.currentData()
        if self._usage == "year_divider":
            years = available_calendar_years(self._photos)
            year = years[0] if years else None
        if year is None:
            self._preview_label.clear()
            self._preview_label.setText(self._translator.tr("calendar_index.no_year"))
            return
        self._preview_label.setPixmap(
            self.render_template_preview(
                width=self._preview_label.width(), height=self._preview_label.height(),
                photos=self._photos, page_attributes={"year": year},
            )
        )
