from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.album.composition import (
    PageComposer,
    PageNumberSettings,
)
from photoalbum.album.pagination import (
    PageSide,
    PlannedPage,
)
from photoalbum.album.planning import PlanItemKind
from photoalbum.album.settings import (
    PhotoCaptionSettings,
    PhotoPageSettings,
)
from photoalbum.rendering.fonts import (
    available_photo_album_fonts,
)
from photoalbum.templates.msb.settings_base import (
    MsbTemplateSettingsWidget,
)


from .caption_style import (
    DEFAULT_CAPTION_COLOR,
    DEFAULT_CAPTION_FONT_SIZE,
    DEFAULT_CAPTION_ORDER,
    caption_color_name,
    caption_font_family,
    caption_font_size,
    caption_order,
    caption_show_datetime,
    caption_show_location,
    caption_show_user,
)


class PhotoPageSettingsWidget(
    MsbTemplateSettingsWidget
):
    """Settings entry point shared by photo-page-1..4."""

    PREVIEW_WIDTH = 360
    PREVIEW_HEIGHT = 510

    _ORDER_LABELS = {
        "caption": "Légende utilisateur",
        "datetime": "Date et heure",
        "break": "─────── saut de ligne ───────",
        "location": "Lieu",
    }

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

        self._loading = True
        self._caption_color = caption_color_name(
            self._instance.settings
        )

        self._create_content()
        self._load_state()

        self._loading = False
        self._render_preview()

    def _create_content(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(24)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        left_layout.addWidget(
            self.create_page_settings_title()
        )

        caption_group = QGroupBox("Légendes")
        caption_layout = QVBoxLayout(caption_group)

        self._show_caption = QCheckBox(
            "Afficher la légende utilisateur"
        )
        self._show_datetime = QCheckBox(
            "Afficher la date et l'heure"
        )
        self._show_location = QCheckBox(
            "Afficher le lieu"
        )

        caption_layout.addWidget(self._show_caption)
        caption_layout.addWidget(self._show_datetime)
        caption_layout.addWidget(self._show_location)

        style_form = QFormLayout()

        self._font = QComboBox()
        for family in available_photo_album_fonts():
            self._font.addItem(family, family)

        self._size = QDoubleSpinBox()
        self._size.setRange(1.0, 300.0)
        self._size.setDecimals(1)
        self._size.setSingleStep(0.5)
        self._size.setSuffix(" pt")

        self._color_button = QPushButton()
        self._color_button.clicked.connect(
            self._choose_color
        )

        style_form.addRow("Police", self._font)
        style_form.addRow("Taille", self._size)
        style_form.addRow("Couleur", self._color_button)

        caption_layout.addLayout(style_form)

        caption_layout.addWidget(QLabel("Disposition"))

        self._order_list = QListWidget()
        self._order_list.setMaximumHeight(120)
        caption_layout.addWidget(self._order_list)

        move_controls = QHBoxLayout()

        self._up = QPushButton("↑")
        self._down = QPushButton("↓")

        self._up.clicked.connect(
            lambda checked=False: self._move_order(-1)
        )
        self._down.clicked.connect(
            lambda checked=False: self._move_order(1)
        )

        move_controls.addWidget(self._up)
        move_controls.addWidget(self._down)
        move_controls.addStretch()

        caption_layout.addLayout(move_controls)
        left_layout.addWidget(caption_group)

        left_layout.addSpacing(12)
        left_layout.addWidget(
            self.create_msb_theme_group()
        )
        left_layout.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        right_layout.addWidget(
            self.create_preview_title()
        )

        self._preview_label = self.create_preview_label(
            self.PREVIEW_WIDTH,
            self.PREVIEW_HEIGHT,
        )

        right_layout.addWidget(
            self._preview_label,
            alignment=Qt.AlignmentFlag.AlignTop,
        )
        right_layout.addStretch()

        root.addWidget(left, 1)
        root.addWidget(right, 0)

        self._show_caption.toggled.connect(
            self._changed
        )
        self._show_datetime.toggled.connect(
            self._changed
        )
        self._show_location.toggled.connect(
            self._changed
        )
        self._font.currentIndexChanged.connect(
            self._changed
        )
        self._size.valueChanged.connect(
            self._changed
        )

    def _load_state(self) -> None:
        settings = self._instance.settings

        self._show_caption.setChecked(
            caption_show_user(settings)
        )
        self._show_datetime.setChecked(
            caption_show_datetime(settings)
        )
        self._show_location.setChecked(
            caption_show_location(settings)
        )

        family = caption_font_family(settings)
        index = self._font.findData(family)
        if index >= 0:
            self._font.setCurrentIndex(index)

        self._size.setValue(
            caption_font_size(settings)
        )

        self._order_list.clear()
        for value in caption_order(settings):
            item = QListWidgetItem(
                self._ORDER_LABELS[value]
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                value,
            )
            self._order_list.addItem(item)

        self._update_color_button()

    def _current_order(self) -> list[str]:
        return [
            str(
                self._order_list.item(index).data(
                    Qt.ItemDataRole.UserRole
                )
            )
            for index in range(
                self._order_list.count()
            )
        ]

    def _move_order(self, delta: int) -> None:
        row = self._order_list.currentRow()
        target = row + delta

        if (
            row < 0
            or target < 0
            or target >= self._order_list.count()
        ):
            return

        item = self._order_list.takeItem(row)
        self._order_list.insertItem(target, item)
        self._order_list.setCurrentRow(target)

        self._changed()

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._caption_color),
            self,
            "Couleur des légendes",
        )

        if not color.isValid():
            return

        self._caption_color = color.name()
        self._update_color_button()
        self._changed()

    def _update_color_button(self) -> None:
        self._color_button.setText(
            self._caption_color.upper()
        )
        self._color_button.setStyleSheet(
            "QPushButton {"
            f"background-color: {self._caption_color};"
            "}"
        )

    def _changed(self, *args) -> None:
        if self._loading:
            return

        settings = dict(self._instance.settings)

        settings["photo_caption"] = {
            "show_caption": self._show_caption.isChecked(),
            "show_datetime": self._show_datetime.isChecked(),
            "show_location": self._show_location.isChecked(),
            "font_family": (
                self._font.currentData()
                or caption_font_family(settings)
            ),
            "font_size": self._size.value(),
            "color": self._caption_color,
            "order": self._current_order(),
        }

        self._instance = replace(
            self._instance,
            settings=settings,
        )

        self.instance_changed.emit()
        self._render_preview()

    def msb_theme_changed(self) -> None:
        self._render_preview()

    def _render_preview(self) -> None:
        try:
            capacity = int(self._instance.template_id.rsplit("-", 1)[1])
        except (ValueError, IndexError):
            capacity = 1
        capacity = max(1, min(4, capacity))
        photos = tuple(self._photos[:capacity])
        page = PlannedPage(
            number=1, side=PageSide.RIGHT, kind=PlanItemKind.PHOTO_GROUP,
            template_id=self._instance.template_id, photos=photos,
            photo_capacity=capacity, page_instance=self._instance,
        )
        photo_settings = PhotoPageSettings(
            page=self._instance,
            caption=PhotoCaptionSettings(
                show_datetime=caption_show_datetime(self._instance.settings),
                show_location=caption_show_location(self._instance.settings),
            ),
        )
        composition = PageComposer().compose(
            page, photo_settings, PageNumberSettings(enabled=False),
            page_width_mm=self._page_format.width_mm,
            page_height_mm=self._page_format.height_mm,
        )
        self._preview_label.setPixmap(
            self.render_composition_preview(
                composition, width=self.PREVIEW_WIDTH, height=self.PREVIEW_HEIGHT,
                project_photos=photos, show_empty_slots=True,
            )
        )
