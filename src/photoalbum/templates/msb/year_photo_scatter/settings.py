from __future__ import annotations

from dataclasses import replace
from secrets import randbelow

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from photoalbum.rendering.fonts import (
    available_photo_album_fonts,
)
from .title_style import (
    title_font_family,
    title_font_size,
)

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.templates.msb.year_photo_scatter.composition import (
    compose_cover_scatter,
    cover_period_title,
)

from photoalbum.gui.preview_render_service import (
    PREVIEW_RENDER_HEIGHT,
    PREVIEW_RENDER_WIDTH,
    PreviewRenderService,
)

from photoalbum.templates.msb.settings_base import (
    MsbTemplateSettingsWidget,
)


class YearPhotoScatterSettingsWidget(
    MsbTemplateSettingsWidget
):
    PREVIEW_WIDTH = 420
    PREVIEW_HEIGHT = 594

    DEFAULT_TITLE_COLOR = "#d0d0d0"

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

        self._shared_render_service = (
            render_service
            or PreviewRenderService(
                self._translator,
                self,
            )
        )

        self._render_service = self._shared_render_service
        self._shared_render_key = None

        self._shared_render_service.preview_ready.connect(
            self._shared_preview_ready
        )

        self._shared_render_service.preview_failed.connect(
            self._shared_preview_failed
        )


        self._load_state()
        self._create_content()
        self._update_controls()
        self._request_preview()

    def _load_state(
        self,
    ) -> None:
        scatter = self._instance.settings.get(
            "scatter",
            {},
        )

        if not isinstance(
            scatter,
            dict,
        ):
            scatter = {}

        self._seeds = [
            int(value)
            for value in scatter.get(
                "seeds",
                [0],
            )
        ] or [0]

        self._index = min(
            max(
                int(
                    scatter.get(
                        "selected_seed_index",
                        0,
                    )
                ),
                0,
            ),
            len(self._seeds) - 1,
        )

        self._title_color = str(
            scatter.get(
                "title_color",
                self.DEFAULT_TITLE_COLOR,
            )
        )

        if not QColor(
            self._title_color
        ).isValid():
            self._title_color = (
                self.DEFAULT_TITLE_COLOR
            )

    def _create_content(
        self,
    ) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(28)

        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(
            self.create_page_settings_title()
        )

        self._proposal_label = QLabel()

        layout.addWidget(
            self._proposal_label
        )

        proposal_controls = QHBoxLayout()

        self._previous_button = QPushButton(
            self._translator.tr(
                "album.cover_previous"
            )
        )

        self._new_button = QPushButton(
            self._translator.tr(
                "album.cover_new"
            )
        )

        self._next_button = QPushButton(
            self._translator.tr(
                "album.cover_next"
            )
        )

        self._previous_button.clicked.connect(
            self._previous
        )

        self._new_button.clicked.connect(
            self._new
        )

        self._next_button.clicked.connect(
            self._next
        )

        proposal_controls.addWidget(
            self._previous_button
        )
        proposal_controls.addWidget(
            self._new_button
        )
        proposal_controls.addWidget(
            self._next_button
        )

        layout.addLayout(
            proposal_controls
        )

        color_controls = QHBoxLayout()

        self._title_color_button = QPushButton()

        self._title_color_button.clicked.connect(
            self._choose_title_color
        )

        self._update_title_color_button()

        size_label = QLabel(
            self._translator.tr(
                "page_settings.title_font_size"
            )
        )

        font_label = QLabel(
            self._translator.tr(
                "page_settings.title_font_family"
            )
        )

        self._title_font_combo = QComboBox()

        for family in available_photo_album_fonts():
            self._title_font_combo.addItem(
                family,
                family,
            )

        current_family = title_font_family(
            self._instance.settings
        )
        font_index = self._title_font_combo.findData(
            current_family
        )
        if font_index >= 0:
            self._title_font_combo.setCurrentIndex(
                font_index
            )

        font_label.setBuddy(
            self._title_font_combo
        )

        self._title_font_size_spin = QDoubleSpinBox()
        self._title_font_size_spin.setRange(1, 300)
        self._title_font_size_spin.setDecimals(1)
        self._title_font_size_spin.setSuffix(" pt")
        self._title_font_size_spin.setValue(
            title_font_size(
                self._instance.settings,
                cover_period_title(
                    self._photos,
                    self._translator.month_name,
                ),
            )
        )

        size_label.setBuddy(
            self._title_font_size_spin
        )

        color_controls.addWidget(
            self._title_color_button
        )
        color_controls.addWidget(
            font_label
        )
        color_controls.addWidget(
            self._title_font_combo
        )
        color_controls.addWidget(
            size_label
        )
        color_controls.addWidget(
            self._title_font_size_spin
        )
        color_controls.addStretch()

        layout.addLayout(
            color_controls
        )

        self._title_font_combo.currentIndexChanged.connect(
            self._change_title_font_family
        )

        self._title_font_size_spin.valueChanged.connect(
            self._change_title_font_size
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

        layout.addSpacing(12)
        layout.addWidget(
            self.create_msb_theme_group()
        )

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_layout.addWidget(
            self.create_preview_title()
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
        self._request_preview()

    def _save_state(
        self,
    ) -> None:
        settings = dict(
            self._instance.settings
        )

        scatter = settings.get("scatter", {})
        settings["scatter"] = {
            **(scatter if isinstance(scatter, dict) else {}),
            "seeds": list(
                self._seeds
            ),
            "selected_seed_index": (
                self._index
            ),
            "title_color": (
                self._title_color
            ),
        }

        self._instance = replace(
            self._instance,
            settings=settings,
        )

        self.instance_changed.emit()

    def _update_controls(
        self,
    ) -> None:
        self._proposal_label.setText(
            self._translator.tr(
                "album.cover_proposal",
                current=self._index + 1,
                total=len(self._seeds),
            )
        )

        self._previous_button.setEnabled(
            self._index > 0
        )

        self._next_button.setEnabled(
            self._index
            < len(self._seeds) - 1
        )

    def _previous(
        self,
    ) -> None:
        if self._index <= 0:
            return

        self._index -= 1

        self._save_state()
        self._update_controls()
        self._request_preview()

    def _next(
        self,
    ) -> None:
        if (
            self._index
            >= len(self._seeds) - 1
        ):
            return

        self._index += 1

        self._save_state()
        self._update_controls()
        self._request_preview()

    def _new(
        self,
    ) -> None:
        self._seeds.append(
            randbelow(
                2_147_483_647
            )
        )

        self._index = (
            len(self._seeds) - 1
        )

        # Avoid keeping an unlimited history.
        if len(self._seeds) > 20:
            self._seeds = (
                self._seeds[-20:]
            )

            self._index = (
                len(self._seeds) - 1
            )

        self._save_state()
        self._update_controls()
        self._request_preview()

    def _update_title_color_button(
        self,
    ) -> None:
        # Keep the native button appearance readable,
        # independently from the selected title color.
        self._title_color_button.setStyleSheet(
            ""
        )

        self._title_color_button.setText(
            self._translator.tr(
                "page_settings.title_color_value",
                color=self._title_color,
            )
        )

    def _choose_title_color(
        self,
    ) -> None:
        color = QColorDialog.getColor(
            QColor(
                self._title_color
            ),
            self,
            self._translator.tr(
                "page_settings.choose_title_color"
            ),
        )

        if not color.isValid():
            return

        self._title_color = color.name()

        self._update_title_color_button()
        self._save_state()

        # Only the title color changed. No need to decode
        # hundreds of photographs again.
        self._request_preview()

    def _change_title_font_family(self, index: int) -> None:
        family = self._title_font_combo.itemData(
            index
        )
        if not family:
            return

        settings = dict(self._instance.settings)
        scatter = settings.get("scatter", {})
        settings["scatter"] = {
            **(scatter if isinstance(scatter, dict) else {}),
            "title_font_family": str(family),
        }
        self._instance = replace(
            self._instance,
            settings=settings,
        )
        self.instance_changed.emit()
        self._request_preview()

    def _change_title_font_size(self, value: float) -> None:
        settings = dict(self._instance.settings)
        scatter = settings.get("scatter", {})
        settings["scatter"] = {
            **(scatter if isinstance(scatter, dict) else {}),
            "title_font_size": value,
        }
        self._instance = replace(self._instance, settings=settings)
        self.instance_changed.emit()
        self._request_preview()

    def _request_preview(
        self,
    ) -> None:
        def set_waiting_key(key):
            self._shared_render_key = key

        self._preview_label.setPixmap(
            self.render_template_preview(
                width=self.PREVIEW_WIDTH,
                height=self.PREVIEW_HEIGHT,
                photos=self._photos,
                set_waiting_key=set_waiting_key,
            )
        )

    def _shared_preview_ready(
        self,
        key,
    ) -> None:
        if key != self._shared_render_key:
            return
        self._request_preview()

    def _shared_preview_failed(
        self,
        key,
        message: str,
    ) -> None:
        if (
            key
            != self._shared_render_key
        ):
            return

        self._preview_label.setText(
            self._translator.tr(
                "page_settings.error",
                error=message,
            )
        )
