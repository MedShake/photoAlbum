from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from photoalbum.gui.template_settings.base import (
    PageTemplateSettingsWidget,
)
from photoalbum.rendering.fonts import (
    available_photo_album_fonts,
)

from .title import (
    DEFAULT_TITLE_COLOR,
    TITLE_POSITIONS,
    automatic_title,
    custom_title_text,
    title_color,
    title_font_family,
    title_font_size,
    title_mode,
    title_position,
    title_visible,
)
from .widget_renderer import (
    EXTERNAL_PATH_KEY,
    PHOTO_PATH_KEY,
    SOURCE_EXTERNAL,
    SOURCE_PROJECT,
    SOURCE_TYPE_KEY,
)


class SimplexFullPhotoCoverSettingsWidget(
    PageTemplateSettingsWidget
):
    """
    Settings editor for the Simplex full-photo cover.

    Follow the common template-settings convention:
    controls on the left and a live page preview on the right.
    """

    compact_dialog = False

    PREVIEW_WIDTH = 420

    def __init__(
        self,
        instance,
        photos,
        *,
        translator,
        render_service=None,
        page_format,
        parent=None,
        **kwargs,
    ) -> None:
        super().__init__(
            instance,
            photos,
            translator=translator,
            render_service=render_service,
            page_format=page_format,
            parent=parent,
        )

        self.window().setWindowTitle(
            self._translator.tr(
                "simplex.full-photo-cover.settings-title"
            )
        )

        self._create_content()
        self._load_photos()
        self._load_title_controls()
        self._render_preview()

    def _create_content(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(28)

        # Left column: settings.
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self._photo_group = QGroupBox(
            self._translator.tr(
                "simplex.full-photo-cover.photo-group"
            ),
            self,
        )
        form = QFormLayout(
            self._photo_group
        )

        self._source_combo = QComboBox(self)
        self._source_combo.addItem(
            self._translator.tr(
                "simplex.full-photo-cover.source-project"
            ),
            SOURCE_PROJECT,
        )
        self._source_combo.addItem(
            self._translator.tr(
                "simplex.full-photo-cover.source-external"
            ),
            SOURCE_EXTERNAL,
        )

        form.addRow(
            self._translator.tr(
                "simplex.full-photo-cover.source"
            ),
            self._source_combo,
        )

        self._photo_combo = QComboBox(self)

        self._photo_label = QLabel(
            self._translator.tr(
                "simplex.full-photo-cover.photo"
            ),
            self,
        )
        form.addRow(
            self._photo_label,
            self._photo_combo,
        )

        self._external_path = QLineEdit(self)
        self._external_path.setReadOnly(True)

        self._browse_button = QPushButton(
            self._translator.tr(
                "simplex.full-photo-cover.browse"
            ),
            self,
        )

        external_widget = QWidget(self)
        external_layout = QHBoxLayout(external_widget)
        external_layout.setContentsMargins(0, 0, 0, 0)
        external_layout.addWidget(self._external_path, 1)
        external_layout.addWidget(self._browse_button)

        self._external_label = QLabel(
            self._translator.tr(
                "simplex.full-photo-cover.file"
            ),
            self,
        )
        self._external_widget = external_widget
        form.addRow(
            self._external_label,
            self._external_widget,
        )

        left_layout.addWidget(
            self._photo_group
        )

        self._no_photo_label = QLabel(
            self._translator.tr(
                "simplex.full-photo-cover.no-photo"
            ),
            self,
        )
        self._no_photo_label.setWordWrap(True)
        self._no_photo_label.hide()
        left_layout.addWidget(self._no_photo_label)

        self._create_title_controls(left_layout)

        left_layout.addStretch()

        self._preview_label = self.create_preview_label(self.PREVIEW_WIDTH)
        self.add_settings_columns(root, left, self._preview_label)

        self._photo_combo.currentIndexChanged.connect(
            self._selection_changed
        )
        self._source_combo.currentIndexChanged.connect(
            self._source_changed
        )
        self._browse_button.clicked.connect(
            self._browse_external_photo
        )

    def _create_title_controls(
        self,
        layout,
    ) -> None:
        self._title_group = QGroupBox(
            self._translator.tr(
                "simplex.full-photo-cover.title-group"
            ),
            self,
        )
        title_layout = QVBoxLayout(
            self._title_group
        )

        self._title_visible_check = QCheckBox(
            self._translator.tr(
                "simplex.full-photo-cover.title-visible"
            ),
            self._title_group,
        )
        title_layout.addWidget(
            self._title_visible_check
        )

        form = QFormLayout()

        self._title_mode_combo = QComboBox(
            self._title_group
        )
        self._title_mode_combo.addItem(
            self._translator.tr(
                "simplex.full-photo-cover.title-mode-automatic"
            ),
            "automatic",
        )
        self._title_mode_combo.addItem(
            self._translator.tr(
                "simplex.full-photo-cover.title-mode-custom"
            ),
            "custom",
        )
        form.addRow(
            self._translator.tr(
                "simplex.full-photo-cover.title-mode"
            ),
            self._title_mode_combo,
        )

        self._title_text_label = QLabel(
            self._translator.tr(
                "simplex.full-photo-cover.custom-title"
            ),
            self._title_group,
        )
        self._title_text_edit = QTextEdit(
            self._title_group
        )
        self._title_text_edit.setPlaceholderText(
            self._translator.tr(
                "simplex.full-photo-cover.custom-title-placeholder"
            )
        )

        metrics = self._title_text_edit.fontMetrics()
        margin = int(
            self._title_text_edit.document().documentMargin()
        )
        frame = self._title_text_edit.frameWidth()
        self._title_text_edit.setFixedHeight(
            metrics.lineSpacing() * 3
            + margin * 2
            + frame * 2
        )

        form.addRow(
            self._title_text_label,
            self._title_text_edit,
        )

        self._title_position_combo = QComboBox(
            self._title_group
        )

        position_keys = {
            "very_high": "simplex.full-photo-cover.title-position-very-high",
            "high": "simplex.full-photo-cover.title-position-high",
            "upper_middle": "simplex.full-photo-cover.title-position-upper-middle",
            "center": "simplex.full-photo-cover.title-position-center",
            "lower_middle": "simplex.full-photo-cover.title-position-lower-middle",
            "low": "simplex.full-photo-cover.title-position-low",
            "very_low": "simplex.full-photo-cover.title-position-very-low",
        }

        for position in TITLE_POSITIONS:
            self._title_position_combo.addItem(
                self._translator.tr(
                    position_keys[position]
                ),
                position,
            )

        form.addRow(
            self._translator.tr(
                "simplex.full-photo-cover.title-position"
            ),
            self._title_position_combo,
        )

        self._title_color_button = QPushButton(
            self._title_group
        )
        form.addRow(
            self._translator.tr(
                "simplex.full-photo-cover.title-color"
            ),
            self._title_color_button,
        )

        self._title_font_combo = QComboBox(
            self._title_group
        )
        for family in available_photo_album_fonts():
            self._title_font_combo.addItem(
                family,
                family,
            )

        form.addRow(
            self._translator.tr(
                "simplex.full-photo-cover.title-font"
            ),
            self._title_font_combo,
        )

        self._title_font_size_spin = QDoubleSpinBox(
            self._title_group
        )
        self._title_font_size_spin.setRange(
            1,
            300,
        )
        self._title_font_size_spin.setDecimals(1)
        self._title_font_size_spin.setSuffix(" pt")

        form.addRow(
            self._translator.tr(
                "simplex.full-photo-cover.title-size"
            ),
            self._title_font_size_spin,
        )

        title_layout.addLayout(form)
        layout.addWidget(self._title_group)

        self._title_visible_check.toggled.connect(
            self._title_visibility_changed
        )
        self._title_mode_combo.currentIndexChanged.connect(
            self._title_mode_changed
        )
        self._title_text_edit.textChanged.connect(
            self._title_text_changed
        )
        self._title_position_combo.currentIndexChanged.connect(
            self._title_position_changed
        )
        self._title_color_button.clicked.connect(
            self._choose_title_color
        )
        self._title_font_combo.currentIndexChanged.connect(
            self._title_font_changed
        )
        self._title_font_size_spin.valueChanged.connect(
            self._title_size_changed
        )

    def _load_title_controls(self) -> None:
        settings = self._instance.settings

        self._title_visible_check.blockSignals(True)
        self._title_mode_combo.blockSignals(True)
        self._title_text_edit.blockSignals(True)
        self._title_position_combo.blockSignals(True)
        self._title_font_combo.blockSignals(True)
        self._title_font_size_spin.blockSignals(True)

        self._title_visible_check.setChecked(
            title_visible(settings)
        )

        mode_index = self._title_mode_combo.findData(
            title_mode(settings)
        )
        self._title_mode_combo.setCurrentIndex(
            max(0, mode_index)
        )

        self._title_text_edit.setPlainText(
            custom_title_text(settings)
        )

        position_index = (
            self._title_position_combo.findData(
                title_position(settings)
            )
        )
        self._title_position_combo.setCurrentIndex(
            max(0, position_index)
        )

        family_index = self._title_font_combo.findData(
            title_font_family(settings)
        )
        if family_index >= 0:
            self._title_font_combo.setCurrentIndex(
                family_index
            )

        automatic = automatic_title(
            self._photos,
            self._translator.month_name,
        )
        self._title_font_size_spin.setValue(
            title_font_size(
                settings,
                automatic,
            )
        )

        self._title_visible_check.blockSignals(False)
        self._title_mode_combo.blockSignals(False)
        self._title_text_edit.blockSignals(False)
        self._title_position_combo.blockSignals(False)
        self._title_font_combo.blockSignals(False)
        self._title_font_size_spin.blockSignals(False)

        self._update_title_color_button()
        self._update_title_controls()

    def _update_title_controls(self) -> None:
        enabled = self._title_visible_check.isChecked()
        custom = (
            self._title_mode_combo.currentData()
            == "custom"
        )

        self._title_mode_combo.setEnabled(enabled)

        self._title_text_label.setVisible(custom)
        self._title_text_edit.setVisible(custom)
        self._title_text_label.setEnabled(
            enabled and custom
        )
        self._title_text_edit.setEnabled(
            enabled and custom
        )

        self._title_position_combo.setEnabled(enabled)
        self._title_color_button.setEnabled(enabled)
        self._title_font_combo.setEnabled(enabled)
        self._title_font_size_spin.setEnabled(enabled)

    def _update_title_color_button(self) -> None:
        color = title_color(
            self._instance.settings
        )
        self._title_color_button.setText(color)
        self._title_color_button.setStyleSheet(
            f"background-color: {color};"
        )

    def _save_title_settings(
        self,
        **changes,
    ) -> None:
        settings = dict(
            self._instance.settings
        )
        current = settings.get(
            "title",
            {},
        )
        if not isinstance(current, dict):
            current = {}

        settings["title"] = {
            **current,
            **changes,
        }

        self._instance = (
            self._instance.with_settings(
                settings
            )
        )

        self.instance_changed.emit()
        self._render_preview()

    def _title_visibility_changed(
        self,
        checked: bool,
    ) -> None:
        self._save_title_settings(
            visible=bool(checked)
        )
        self._update_title_controls()

    def _title_mode_changed(
        self,
        index: int,
    ) -> None:
        mode = self._title_mode_combo.itemData(
            index
        )
        if mode not in {
            "automatic",
            "custom",
        }:
            return

        self._save_title_settings(
            mode=str(mode)
        )
        self._update_title_controls()

    def _title_text_changed(self) -> None:
        self._save_title_settings(
            text=self._title_text_edit.toPlainText()
        )

    def _title_position_changed(
        self,
        index: int,
    ) -> None:
        position = (
            self._title_position_combo.itemData(
                index
            )
        )
        if position not in TITLE_POSITIONS:
            return

        self._save_title_settings(
            position=str(position)
        )

    def _choose_title_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(
                title_color(
                    self._instance.settings
                )
            ),
            self,
            self._translator.tr(
                "simplex.full-photo-cover.choose-title-color"
            ),
        )

        if not color.isValid():
            return

        self._save_title_settings(
            color=color.name()
        )
        self._update_title_color_button()

    def _title_font_changed(
        self,
        index: int,
    ) -> None:
        family = self._title_font_combo.itemData(
            index
        )
        if not family:
            return

        self._save_title_settings(
            font_family=str(family)
        )

    def _title_size_changed(
        self,
        value: float,
    ) -> None:
        self._save_title_settings(
            font_size=float(value)
        )

    def _load_photos(self) -> None:
        selected_path = str(
            self._instance.settings.get(
                PHOTO_PATH_KEY,
                "",
            )
        )

        selected_index = -1

        self._photo_combo.blockSignals(True)
        self._photo_combo.clear()

        for index, photo in enumerate(self._photos):
            path = str(photo.path)

            label = Path(path).name

            capture_datetime = getattr(
                photo,
                "capture_datetime",
                None,
            )

            if capture_datetime is not None:
                label = (
                    f"{capture_datetime:%Y-%m-%d %H:%M} — "
                    f"{label}"
                )

            self._photo_combo.addItem(
                label,
                path,
            )

            if path == selected_path:
                selected_index = index

        if selected_index >= 0:
            self._photo_combo.setCurrentIndex(
                selected_index
            )
        elif self._photo_combo.count():
            self._photo_combo.setCurrentIndex(0)

            # Keep the instance consistent with the default
            # selection shown by the editor.
            settings = dict(
                self._instance.settings
            )
            settings[PHOTO_PATH_KEY] = (
                self._photo_combo.currentData()
            )
            self._instance = (
                self._instance.with_settings(
                    settings
                )
            )

        has_photos = bool(
            self._photo_combo.count()
        )

        self._photo_combo.setEnabled(has_photos)
        self._no_photo_label.setVisible(
            not has_photos
        )

        self._photo_combo.blockSignals(False)

        source_type = str(
            self._instance.settings.get(
                SOURCE_TYPE_KEY,
                SOURCE_PROJECT,
            )
        )

        self._external_path.setText(
            str(
                self._instance.settings.get(
                    EXTERNAL_PATH_KEY,
                    "",
                )
            )
        )

        self._source_combo.blockSignals(True)

        source_index = self._source_combo.findData(
            source_type
        )
        if source_index < 0:
            source_index = self._source_combo.findData(
                SOURCE_PROJECT
            )

        self._source_combo.setCurrentIndex(
            source_index
        )
        self._source_combo.blockSignals(False)

        self._update_source_controls()

    def _update_source_controls(self) -> None:
        project_source = (
            self._source_combo.currentData()
            == SOURCE_PROJECT
        )
        has_project_photos = (
            self._photo_combo.count() > 0
        )

        self._photo_label.setVisible(
            project_source
            and has_project_photos
        )
        self._photo_combo.setVisible(
            project_source
            and has_project_photos
        )
        self._photo_combo.setEnabled(
            project_source
            and has_project_photos
        )

        self._no_photo_label.setVisible(
            project_source
            and not has_project_photos
        )

        self._external_label.setVisible(
            not project_source
        )
        self._external_widget.setVisible(
            not project_source
        )

    def _source_changed(
        self,
        index: int,
    ) -> None:
        source_type = self._source_combo.itemData(
            index
        )

        if source_type not in {
            SOURCE_PROJECT,
            SOURCE_EXTERNAL,
        }:
            return

        settings = dict(self._instance.settings)
        settings[SOURCE_TYPE_KEY] = source_type

        self._instance = self._instance.with_settings(
            settings
        )

        self._update_source_controls()
        self.instance_changed.emit()
        self._render_preview()

    def _browse_external_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._translator.tr(
                "simplex.full-photo-cover.choose-file"
            ),
            self._external_path.text().strip(),
            self._translator.tr(
                "simplex.full-photo-cover.image-filter"
            ),
        )

        if not path:
            return

        self._external_path.setText(path)

        settings = dict(self._instance.settings)
        settings[EXTERNAL_PATH_KEY] = path
        settings[SOURCE_TYPE_KEY] = SOURCE_EXTERNAL

        self._instance = self._instance.with_settings(
            settings
        )

        source_index = self._source_combo.findData(
            SOURCE_EXTERNAL
        )
        if source_index >= 0:
            self._source_combo.blockSignals(True)
            self._source_combo.setCurrentIndex(
                source_index
            )
            self._source_combo.blockSignals(False)

        self._update_source_controls()
        self.instance_changed.emit()
        self._render_preview()

    def _selection_changed(
        self,
        index: int,
    ) -> None:
        if index < 0:
            return

        settings = dict(
            self._instance.settings
        )

        settings[PHOTO_PATH_KEY] = (
            self._photo_combo.itemData(index)
        )

        self._instance = (
            self._instance.with_settings(
                settings
            )
        )

        self.instance_changed.emit()
        self._render_preview()

    def _render_preview(self) -> None:
        self._preview_label.setPixmap(
            self.render_template_preview(
                width=self._preview_label.width(),
                height=self._preview_label.height(),
                photos=self._photos,
            )
        )

    def instance(self):
        return self._instance
