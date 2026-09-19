from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from photoalbum.gui.template_settings.base import (
    PageTemplateSettingsWidget,
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
        self._render_preview()

    def _create_content(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(28)

        # Left column: settings.
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        form = QFormLayout()

        self._project_source_radio = QRadioButton(
            self._translator.tr(
                "simplex.full-photo-cover.source-project"
            ),
            self,
        )
        self._external_source_radio = QRadioButton(
            self._translator.tr(
                "simplex.full-photo-cover.source-external"
            ),
            self,
        )

        source_widget = QWidget(self)
        source_layout = QVBoxLayout(source_widget)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self._project_source_radio)
        source_layout.addWidget(self._external_source_radio)

        form.addRow(
            self._translator.tr(
                "simplex.full-photo-cover.source"
            ),
            source_widget,
        )

        self._photo_combo = QComboBox(self)

        form.addRow(
            self._translator.tr(
                "simplex.full-photo-cover.photo"
            ),
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

        form.addRow(
            self._translator.tr(
                "simplex.full-photo-cover.file"
            ),
            external_widget,
        )

        left_layout.addLayout(form)

        self._no_photo_label = QLabel(
            self._translator.tr(
                "simplex.full-photo-cover.no-photo"
            ),
            self,
        )
        self._no_photo_label.setWordWrap(True)
        self._no_photo_label.hide()
        left_layout.addWidget(self._no_photo_label)

        left_layout.addStretch()

        self._preview_label = self.create_preview_label(self.PREVIEW_WIDTH)
        self.add_settings_columns(root, left, self._preview_label)

        self._photo_combo.currentIndexChanged.connect(
            self._selection_changed
        )
        self._project_source_radio.toggled.connect(
            self._source_changed
        )
        self._external_source_radio.toggled.connect(
            self._source_changed
        )
        self._browse_button.clicked.connect(
            self._browse_external_photo
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

        self._project_source_radio.blockSignals(True)
        self._external_source_radio.blockSignals(True)

        if source_type == SOURCE_EXTERNAL:
            self._external_source_radio.setChecked(True)
        else:
            self._project_source_radio.setChecked(True)

        self._project_source_radio.blockSignals(False)
        self._external_source_radio.blockSignals(False)

        self._update_source_controls()

    def _update_source_controls(self) -> None:
        project_source = (
            self._project_source_radio.isChecked()
        )

        self._photo_combo.setEnabled(
            project_source
            and self._photo_combo.count() > 0
        )
        self._no_photo_label.setVisible(
            project_source
            and self._photo_combo.count() == 0
        )
        self._external_path.setEnabled(
            not project_source
        )
        self._browse_button.setEnabled(
            not project_source
        )

    def _source_changed(self) -> None:
        if self._external_source_radio.isChecked():
            source_type = SOURCE_EXTERNAL
        else:
            source_type = SOURCE_PROJECT

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

        self._external_source_radio.setChecked(True)

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
