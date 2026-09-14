from __future__ import annotations

from dataclasses import replace
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
    QDialog,
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
from photoalbum.i18n import Translator

from .cover_render_worker import (
    CoverRenderWorker,
)


class PageInstanceDialog(QDialog):
    PREVIEW_WIDTH = 420
    PREVIEW_HEIGHT = 594

    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator: Translator,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._instance = instance
        self._photos = list(photos)
        self._translator = translator

        self._request_id: str | None = None
        self._composition_title = ""

        self.setWindowTitle(
            self._translator.tr(
                "page_settings.title"
            )
        )

        self._create_content()

        if (
            self._instance.template_id
            == "year-photo-scatter"
        ):
            self._load_scatter_state()
            self._update_controls()
            self._request_preview()
        else:
            self._preview_label.setText(
                self._translator.tr(
                    "page_settings.no_options"
                )
            )

    def _create_content(self) -> None:
        layout = QVBoxLayout(self)

        self._template_label = QLabel(
            self._instance.template_id
        )

        font = QFont(
            self._template_label.font()
        )
        font.setBold(True)
        self._template_label.setFont(font)

        layout.addWidget(
            self._template_label
        )

        self._proposal_label = QLabel()
        layout.addWidget(
            self._proposal_label
        )

        controls = QHBoxLayout()

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

        controls.addWidget(
            self._previous_button
        )
        controls.addWidget(
            self._new_button
        )
        controls.addWidget(
            self._next_button
        )

        layout.addLayout(controls)

        color_controls = QHBoxLayout()

        self._title_color_button = QPushButton(
            self._translator.tr(
                "page_settings.title_color"
            )
        )

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
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        close_button = QPushButton(
            self._translator.tr(
                "page_settings.close"
            )
        )
        close_button.clicked.connect(
            self.accept
        )

        layout.addWidget(
            close_button,
            alignment=Qt.AlignmentFlag.AlignRight,
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

    def _load_scatter_state(self) -> None:
        scatter = self._instance.settings.get(
            "scatter",
            {},
        )

        if not isinstance(scatter, dict):
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
                "#d0d0d0",
            )
        )

        if not QColor(
            self._title_color
        ).isValid():
            self._title_color = "#d0d0d0"

        self._update_title_color_button()

    def _save_scatter_state(self) -> None:
        settings = dict(
            self._instance.settings
        )

        settings["scatter"] = {
            "seeds": list(self._seeds),
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

    def _update_controls(self) -> None:
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

    def _update_title_color_button(
        self,
    ) -> None:
        color = QColor(
            self._title_color
        )

        self._title_color_button.setStyleSheet(
            ""
        )

        self._title_color_button.setText(
            self._translator.tr(
                "page_settings.title_color_value",
                color=color.name(),
            )
        )


    def _choose_title_color(
        self,
    ) -> None:
        initial = QColor(
            self._title_color
        )

        color = QColorDialog.getColor(
            initial,
            self,
            self._translator.tr(
                "page_settings.choose_title_color"
            ),
        )

        if not color.isValid():
            return

        self._title_color = color.name()

        self._update_title_color_button()
        self._save_scatter_state()

        # No need to regenerate the photo mosaic:
        # only the overlaid title changes.
        if (
            hasattr(
                self,
                "_preview_label",
            )
            and self._preview_label.pixmap()
            is not None
        ):
            self._request_preview()

    def _previous(self) -> None:
        if self._index <= 0:
            return

        self._index -= 1
        self._save_scatter_state()
        self._update_controls()
        self._request_preview()

    def _next(self) -> None:
        if self._index >= len(self._seeds) - 1:
            return

        self._index += 1
        self._save_scatter_state()
        self._update_controls()
        self._request_preview()

    def _new(self) -> None:
        from secrets import randbelow

        self._seeds.append(
            randbelow(
                2_147_483_647
            )
        )

        self._index = (
            len(self._seeds) - 1
        )

        if len(self._seeds) > 20:
            self._seeds = self._seeds[-20:]
            self._index = len(self._seeds) - 1

        self._save_scatter_state()
        self._update_controls()
        self._request_preview()

    def _request_preview(self) -> None:
        self._preview_label.setText(
            self._translator.tr(
                "page_settings.calculating"
            )
        )

        request_id = uuid4().hex
        self._request_id = request_id

        composition = compose_cover_scatter(
            self._photos,
            seed=self._seeds[self._index],
            month_name=(
                self._translator.month_name
            ),
        )

        self._composition_title = (
            composition.title
        )

        worker = CoverRenderWorker(
            request_id=request_id,
            width=self.PREVIEW_WIDTH,
            height=self.PREVIEW_HEIGHT,
            items=visible_cover_scatter_items(
                composition.items
            ),
        )

        worker.signals.finished.connect(
            self._preview_ready
        )

        worker.signals.failed.connect(
            self._preview_failed
        )

        QThreadPool.globalInstance().start(
            worker
        )

    def _preview_ready(
        self,
        request_id: str,
        data: bytes,
    ) -> None:
        if request_id != self._request_id:
            return

        pixmap = QPixmap()
        pixmap.loadFromData(data)

        if pixmap.isNull():
            self._preview_failed(
                request_id,
                "Invalid image",
            )
            return

        painter = QPainter(pixmap)

        font = QFont(
            painter.font()
        )
        font.setBold(True)
        font.setPixelSize(72)
        painter.setFont(font)

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

    def _preview_failed(
        self,
        request_id: str,
        message: str,
    ) -> None:
        if request_id != self._request_id:
            return

        self._preview_label.setText(
            self._translator.tr(
                "page_settings.error",
                error=message,
            )
        )

    def instance(self) -> PageInstance:
        return self._instance
