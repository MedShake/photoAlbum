from __future__ import annotations

from dataclasses import replace
from secrets import randbelow
from uuid import uuid4

from PySide6.QtCore import (
    Qt,
    QThreadPool,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from photoalbum.album import PageInstance
from photoalbum.album.cover_scatter import (
    compose_cover_scatter,
    visible_cover_scatter_items,
)
from photoalbum.gui.cover_render_worker import (
    CoverRenderWorker,
)

from photoalbum.gui.preview_render_service import (
    PREVIEW_RENDER_HEIGHT,
    PREVIEW_RENDER_WIDTH,
    PreviewRenderService,
)

from .base import PageTemplateSettingsWidget


class YearPhotoScatterSettingsWidget(
    PageTemplateSettingsWidget
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
        parent=None,
    ) -> None:
        super().__init__(
            instance,
            photos,
            translator=translator,
            render_service=render_service,
            parent=parent,
        )

        self._shared_render_service = (
            render_service
            or PreviewRenderService(
                self._translator,
                self,
            )
        )

        self._shared_render_key = None

        self._shared_render_service.preview_ready.connect(
            self._shared_preview_ready
        )

        self._shared_render_service.preview_failed.connect(
            self._shared_preview_failed
        )


        self._base_pixmap = QPixmap()
        self._composition_title = ""

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
        layout = QVBoxLayout(
            self
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

        color_controls.addWidget(
            self._title_color_button
        )

        color_controls.addStretch()

        layout.addLayout(
            color_controls
        )

        self._update_title_color_button()

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

    def _save_state(
        self,
    ) -> None:
        settings = dict(
            self._instance.settings
        )

        settings["scatter"] = {
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
        self._display_preview()

    def _request_preview(
        self,
    ) -> None:
        composition = compose_cover_scatter(
            list(
                self._photos
            ),
            seed=self._seeds[
                self._index
            ],
            month_name=(
                self._translator.month_name
            ),
        )

        self._composition_title = (
            composition.title
        )

        key = (
            self._shared_render_service.key_for(
                self._instance,
                self._photos,
                width=PREVIEW_RENDER_WIDTH,
                height=PREVIEW_RENDER_HEIGHT,
            )
        )

        self._shared_render_key = key

        pixmap = (
            self._shared_render_service.cached(
                key
            )
        )

        if pixmap is not None:
            self._base_pixmap = pixmap
            self._display_preview()
            return

        self._preview_label.clear()

        self._preview_label.setText(
            self._translator.tr(
                "page_settings.calculating"
            )
        )

        self._shared_render_service.request(
            self._instance,
            self._photos,
            width=PREVIEW_RENDER_WIDTH,
            height=PREVIEW_RENDER_HEIGHT,
        )


    def _shared_preview_ready(
        self,
        key,
    ) -> None:
        if (
            key
            != self._shared_render_key
        ):
            return

        pixmap = (
            self._shared_render_service.cached(
                key
            )
        )

        if pixmap is None:
            return

        self._base_pixmap = pixmap

        self._display_preview()

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

    def _display_preview(
        self,
    ) -> None:
        if self._base_pixmap.isNull():
            return

        pixmap = self._base_pixmap.copy()

        painter = QPainter(
            pixmap
        )

        font = QFont(
            painter.font()
        )

        font.setBold(
            True
        )

        font.setPixelSize(
            72
        )

        painter.setFont(
            font
        )

        painter.setPen(
            QColor(
                self._title_color
            )
        )

        painter.drawText(
            pixmap.rect().adjusted(
                15,
                15,
                -15,
                -15,
            ),
            Qt.AlignmentFlag.AlignCenter,
            self._composition_title,
        )

        painter.end()

        self._preview_label.setPixmap(
            pixmap
        )
