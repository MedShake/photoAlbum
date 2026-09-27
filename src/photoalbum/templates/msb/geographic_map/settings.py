from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
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
from photoalbum.templates.msb.settings_base import (
    MsbTemplateSettingsWidget,
)

from .defaults import (
    DEFAULT_LAND_COLOR,
    DEFAULT_WATER_COLOR,
    DEFAULT_BORDER_COLOR,
    DEFAULT_POINT_COLOR,
    DEFAULT_MARKER_MODE,
    DEFAULT_POINT_COLOR_MODE,
    DEFAULT_POINT_SIZE,
    DEFAULT_POINT_OPACITY,
    DEFAULT_PROJECTION,
)


def geographic_map_settings(
    instance: PageInstance,
) -> dict:
    settings = instance.settings.setdefault(
        "geographic_map",
        {},
    )

    if not isinstance(settings, dict):
        settings = {}
        instance.settings["geographic_map"] = settings

    settings.setdefault("year", None)
    settings.setdefault(
        "projection",
        DEFAULT_PROJECTION,
    )
    settings.setdefault(
        "land_color",
        DEFAULT_LAND_COLOR,
    )
    settings.setdefault(
        "water_color",
        DEFAULT_WATER_COLOR,
    )
    settings.setdefault(
        "border_color",
        DEFAULT_BORDER_COLOR,
    )
    settings.setdefault(
        "marker_mode",
        DEFAULT_MARKER_MODE,
    )
    settings.setdefault(
        "point_color_mode",
        DEFAULT_POINT_COLOR_MODE,
    )
    settings.setdefault(
        "point_color",
        DEFAULT_POINT_COLOR,
    )
    settings.setdefault(
        "point_size",
        DEFAULT_POINT_SIZE,
    )
    settings.setdefault(
        "point_opacity",
        DEFAULT_POINT_OPACITY,
    )
    settings.setdefault(
        "show_month_legend",
        True,
    )

    return settings


class GeographicMapSettingsWidget(
    MsbTemplateSettingsWidget
):
    PREVIEW_WIDTH = 400

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

    def _create_content(self) -> None:
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

        self._projection_combo = QComboBox()

        self._projection_combo.addItem(
            self._translator.tr(
                "page_settings.map_projection_web_mercator"
            ),
            "web_mercator",
        )
        self._projection_combo.addItem(
            self._translator.tr(
                "page_settings.map_projection_equal_earth"
            ),
            "equal_earth",
        )
        self._projection_combo.addItem(
            self._translator.tr(
                "page_settings.map_projection_robinson"
            ),
            "robinson",
        )

        form.addRow(
            self._translator.tr(
                "page_settings.map_projection"
            ),
            self._projection_combo,
        )

        self._land_button = QPushButton()
        self._water_button = QPushButton()
        self._border_button = QPushButton()

        self._land_button.clicked.connect(
            lambda: self._choose_color(
                "land_color",
                self._land_button,
            )
        )
        self._water_button.clicked.connect(
            lambda: self._choose_color(
                "water_color",
                self._water_button,
            )
        )
        self._border_button.clicked.connect(
            lambda: self._choose_color(
                "border_color",
                self._border_button,
            )
        )

        form.addRow(
            self._translator.tr(
                "page_settings.map_land_color"
            ),
            self._land_button,
        )
        form.addRow(
            self._translator.tr(
                "page_settings.map_water_color"
            ),
            self._water_button,
        )
        form.addRow(
            self._translator.tr(
                "page_settings.map_border_color"
            ),
            self._border_button,
        )

        left_layout.addLayout(form)

        points_group = QGroupBox(
            self._translator.tr(
                "page_settings.map_points_group"
            )
        )
        points_form = QFormLayout(points_group)

        self._point_color_mode = QComboBox()
        self._point_color_mode.addItem(
            self._translator.tr(
                "page_settings.map_point_color_month"
            ),
            "month",
        )
        self._point_color_mode.addItem(
            self._translator.tr(
                "page_settings.map_point_color_single"
            ),
            "single",
        )

        self._point_color_button = QPushButton()
        self._point_color_button.clicked.connect(
            lambda: self._choose_color(
                "point_color",
                self._point_color_button,
            )
        )

        self._point_size = QDoubleSpinBox()
        self._point_size.setRange(0.001, 0.015)
        self._point_size.setDecimals(4)
        self._point_size.setSingleStep(0.0005)

        self._point_opacity = QDoubleSpinBox()
        self._point_opacity.setRange(0.05, 1.0)
        self._point_opacity.setDecimals(2)
        self._point_opacity.setSingleStep(0.05)

        self._show_month_legend = QCheckBox(
            self._translator.tr(
                "page_settings.map_show_month_legend"
            )
        )

        points_form.addRow(
            self._translator.tr(
                "page_settings.map_point_color_mode"
            ),
            self._point_color_mode,
        )
        self._point_color_label = QLabel(
            self._translator.tr(
                "page_settings.map_point_color"
            )
        )
        points_form.addRow(
            self._point_color_label,
            self._point_color_button,
        )
        points_form.addRow(
            self._translator.tr(
                "page_settings.map_point_size"
            ),
            self._point_size,
        )
        points_form.addRow(
            self._translator.tr(
                "page_settings.map_point_opacity"
            ),
            self._point_opacity,
        )
        points_form.addRow(
            self._show_month_legend
        )

        left_layout.addWidget(points_group)

        left_layout.addSpacing(12)
        left_layout.addWidget(
            self.create_msb_theme_group()
        )
        left_layout.addStretch(1)

        self._preview_label = self.create_preview_label(
            self.PREVIEW_WIDTH
        )

        self._render_service.preview_ready.connect(
            self._preview_render_ready
        )
        self._render_service.preview_failed.connect(
            self._preview_render_failed
        )
        self.add_settings_columns(
            root,
            left,
            self._preview_label,
        )

        self._year_combo.currentIndexChanged.connect(
            self._year_changed
        )
        self._projection_combo.currentIndexChanged.connect(
            self._projection_changed
        )
        self._point_color_mode.currentIndexChanged.connect(
            self._point_settings_changed
        )
        self._point_size.valueChanged.connect(
            self._point_settings_changed
        )
        self._point_opacity.valueChanged.connect(
            self._point_settings_changed
        )
        self._show_month_legend.toggled.connect(
            self._point_settings_changed
        )

    def _render_preview(self) -> None:
        pixmap = self.render_template_preview(
            width=self._preview_label.width(),
            height=self._preview_label.height(),
            photos=self._photos,
            set_waiting_key=self._set_waiting_preview_key,
        )

        self._preview_label.setPixmap(
            pixmap
        )

    def _set_waiting_preview_key(
        self,
        key,
    ) -> None:
        self._waiting_preview_key = key

    def _preview_render_ready(
        self,
        key,
    ) -> None:
        if key != getattr(
            self,
            "_waiting_preview_key",
            None,
        ):
            return

        self._waiting_preview_key = None
        self._render_preview()

    def _preview_render_failed(
        self,
        key,
        _message: str,
    ) -> None:
        if key != getattr(
            self,
            "_waiting_preview_key",
            None,
        ):
            return

        self._waiting_preview_key = None

    def _load_state(self) -> None:
        settings = geographic_map_settings(
            self._instance
        )

        years = sorted(
            {
                photo.capture_datetime.year
                for photo in self._photos
                if photo.capture_datetime is not None
            }
        )

        self._year_combo.blockSignals(True)
        self._year_combo.clear()

        self._year_combo.addItem(
            self._translator.tr(
                "page_settings.all_photos"
            ),
            None,
        )

        for year in years:
            self._year_combo.addItem(
                str(year),
                year,
            )

        selected_year = settings.get("year")

        index = self._year_combo.findData(
            selected_year
        )
        self._year_combo.setCurrentIndex(
            max(index, 0)
        )
        self._year_combo.blockSignals(False)

        projection_index = (
            self._projection_combo.findData(
                settings.get(
                    "projection",
                    DEFAULT_PROJECTION,
                )
            )
        )

        self._projection_combo.blockSignals(True)
        self._projection_combo.setCurrentIndex(
            max(projection_index, 0)
        )
        self._projection_combo.blockSignals(False)

        self._update_color_button(
            self._land_button,
            settings["land_color"],
        )
        self._update_color_button(
            self._water_button,
            settings["water_color"],
        )
        self._update_color_button(
            self._border_button,
            settings["border_color"],
        )
        self._update_color_button(
            self._point_color_button,
            settings["point_color"],
        )

        point_mode_index = self._point_color_mode.findData(
            settings["point_color_mode"]
        )
        self._point_color_mode.blockSignals(True)
        self._point_color_mode.setCurrentIndex(
            max(point_mode_index, 0)
        )
        self._point_color_mode.blockSignals(False)

        self._point_size.blockSignals(True)
        self._point_size.setValue(
            float(settings["point_size"])
        )
        self._point_size.blockSignals(False)

        self._point_opacity.blockSignals(True)
        self._point_opacity.setValue(
            float(settings["point_opacity"])
        )
        self._point_opacity.blockSignals(False)

        self._show_month_legend.blockSignals(True)
        self._show_month_legend.setChecked(
            bool(settings["show_month_legend"])
        )
        self._show_month_legend.blockSignals(False)

        self._update_point_controls()

    def _year_changed(self) -> None:
        settings = geographic_map_settings(
            self._instance
        )
        settings["year"] = (
            self._year_combo.currentData()
        )
        self._render_preview()

    def _projection_changed(self) -> None:
        settings = geographic_map_settings(
            self._instance
        )

        settings["projection"] = (
            self._projection_combo.currentData()
            or DEFAULT_PROJECTION
        )

        self._render_preview()

    def _point_settings_changed(self) -> None:
        settings = geographic_map_settings(
            self._instance
        )

        settings["point_color_mode"] = (
            self._point_color_mode.currentData()
        )
        settings["point_size"] = (
            self._point_size.value()
        )
        settings["point_opacity"] = (
            self._point_opacity.value()
        )
        settings["show_month_legend"] = (
            self._show_month_legend.isChecked()
        )

        self._update_point_controls()
        self._render_preview()

    def _update_point_controls(self) -> None:
        month_mode = (
            self._point_color_mode.currentData()
            == "month"
        )
        # In month mode the colors come from the MSB
        # monthly palette: a single point color has no meaning.
        self._point_color_label.setVisible(
            not month_mode
        )
        self._point_color_button.setVisible(
            not month_mode
        )

        # Conversely the month legend only has meaning when
        # points actually use the monthly colors.
        self._show_month_legend.setVisible(
            month_mode
        )
        self._show_month_legend.setEnabled(
            month_mode
        )

    def _choose_color(
        self,
        key: str,
        button: QPushButton,
    ) -> None:
        settings = geographic_map_settings(
            self._instance
        )

        current = QColor(
            settings[key]
        )

        color = QColorDialog.getColor(
            current,
            self,
        )

        if not color.isValid():
            return

        settings[key] = color.name()
        self._update_color_button(
            button,
            color.name(),
        )
        self._render_preview()

    @staticmethod
    def _update_color_button(
        button: QPushButton,
        value: str,
    ) -> None:
        color = QColor(value)

        button.setText(value.upper())
        button.setStyleSheet(
            "QPushButton {"
            f"background-color: {color.name()};"
            "padding: 4px 12px;"
            "}"
        )
