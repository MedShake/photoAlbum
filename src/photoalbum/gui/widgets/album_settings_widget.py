from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PhotoPageSettings,
    SpecialPage,
    TemplateKind,
    TemplateRegistry,
)


class AlbumSettingsWidget(QWidget):
    def __init__(
        self,
        registry: TemplateRegistry,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._registry = registry

        self._create_content()
        self._apply_defaults()
        self.set_available_years(set())

    def _create_content(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(self._create_covers_group())
        layout.addWidget(self._create_dividers_group())
        layout.addWidget(self._create_photo_pages_group())

        special_layout = QHBoxLayout()

        special_layout.addWidget(
            self._create_special_pages_group(
                title="Pages after inside front cover",
                list_widget_name="_front_matter_list",
                combo_name="_front_matter_combo",
            )
        )

        special_layout.addWidget(
            self._create_special_pages_group(
                title="Pages before inside back cover",
                list_widget_name="_back_matter_list",
                combo_name="_back_matter_combo",
            )
        )

        layout.addLayout(special_layout)
        layout.addStretch()

    def _create_covers_group(self) -> QGroupBox:
        group = QGroupBox("Covers")
        form = QFormLayout(group)

        self._front_cover_combo = self._create_template_combo(
            TemplateKind.COVER
        )
        self._inside_front_cover_combo = (
            self._create_template_combo(
                TemplateKind.COVER
            )
        )
        self._inside_back_cover_combo = (
            self._create_template_combo(
                TemplateKind.COVER
            )
        )
        self._back_cover_combo = self._create_template_combo(
            TemplateKind.COVER
        )

        form.addRow(
            "Front cover:",
            self._front_cover_combo,
        )
        form.addRow(
            "Inside front cover:",
            self._inside_front_cover_combo,
        )
        form.addRow(
            "Inside back cover:",
            self._inside_back_cover_combo,
        )
        form.addRow(
            "Back cover:",
            self._back_cover_combo,
        )

        return group

    def _create_dividers_group(self) -> QGroupBox:
        group = QGroupBox("Dividers")
        layout = QVBoxLayout(group)

        month_layout = QHBoxLayout()

        self._month_dividers_checkbox = QCheckBox(
            "Month separators"
        )
        self._month_divider_combo = (
            self._create_template_combo(
                TemplateKind.MONTH_DIVIDER
            )
        )
        self._month_placement_combo = (
            self._create_placement_combo()
        )

        month_layout.addWidget(
            self._month_dividers_checkbox
        )
        month_layout.addWidget(
            self._month_divider_combo,
            1,
        )
        month_layout.addWidget(
            self._month_placement_combo,
        )

        layout.addLayout(month_layout)

        year_layout = QHBoxLayout()

        self._year_dividers_checkbox = QCheckBox(
            "Year separators"
        )
        self._year_divider_combo = (
            self._create_template_combo(
                TemplateKind.YEAR_DIVIDER
            )
        )
        self._year_placement_combo = (
            self._create_placement_combo()
        )

        year_layout.addWidget(
            self._year_dividers_checkbox
        )
        year_layout.addWidget(
            self._year_divider_combo,
            1,
        )
        year_layout.addWidget(
            self._year_placement_combo,
        )

        layout.addLayout(year_layout)

        self._year_divider_hint = QLabel()
        layout.addWidget(self._year_divider_hint)

        self._month_dividers_checkbox.toggled.connect(
            self._update_divider_controls
        )
        self._year_dividers_checkbox.toggled.connect(
            self._update_divider_controls
        )

        return group

    def _create_photo_pages_group(self) -> QGroupBox:
        group = QGroupBox("Photo pages")
        form = QFormLayout(group)

        self._photo_page_combo = self._create_template_combo(
            TemplateKind.PHOTO_PAGE
        )

        form.addRow(
            "Template:",
            self._photo_page_combo,
        )

        return group

    def _create_special_pages_group(
        self,
        *,
        title: str,
        list_widget_name: str,
        combo_name: str,
    ) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)

        list_widget = QListWidget()
        setattr(
            self,
            list_widget_name,
            list_widget,
        )

        layout.addWidget(list_widget)

        combo = self._create_template_combo(
            TemplateKind.SPECIAL_PAGE
        )
        setattr(
            self,
            combo_name,
            combo,
        )

        add_layout = QHBoxLayout()
        add_layout.addWidget(combo, 1)

        add_button = QPushButton("Add")
        add_button.clicked.connect(
            lambda checked=False,
            lw=list_widget,
            cb=combo: self._add_special_page(
                lw,
                cb,
            )
        )

        add_layout.addWidget(add_button)
        layout.addLayout(add_layout)

        controls = QHBoxLayout()

        up_button = QPushButton("Up")
        down_button = QPushButton("Down")
        remove_button = QPushButton("Remove")

        up_button.clicked.connect(
            lambda checked=False,
            lw=list_widget: self._move_special_page(
                lw,
                -1,
            )
        )

        down_button.clicked.connect(
            lambda checked=False,
            lw=list_widget: self._move_special_page(
                lw,
                1,
            )
        )

        remove_button.clicked.connect(
            lambda checked=False,
            lw=list_widget: self._remove_special_page(
                lw
            )
        )

        controls.addWidget(up_button)
        controls.addWidget(down_button)
        controls.addWidget(remove_button)

        layout.addLayout(controls)

        return group

    def _create_template_combo(
        self,
        kind: TemplateKind,
    ) -> QComboBox:
        combo = QComboBox()

        for template in self._registry.list_by_kind(kind):
            combo.addItem(
                template.name,
                template.template_id,
            )

        return combo

    @staticmethod
    def _create_placement_combo() -> QComboBox:
        combo = QComboBox()

        combo.addItem(
            "Natural flow",
            DividerPlacement.NATURAL.value,
        )
        combo.addItem(
            "Always on right page",
            DividerPlacement.RIGHT_PAGE.value,
        )
        combo.addItem(
            "Right page with blank facing page",
            DividerPlacement.RIGHT_PAGE_WITH_BLANK_FACING.value,
        )

        return combo

    def _apply_defaults(self) -> None:
        self._set_combo_template(
            self._front_cover_combo,
            "year-photo-scatter",
        )
        self._set_combo_template(
            self._inside_front_cover_combo,
            "geographic-word-cloud",
        )
        self._set_combo_template(
            self._inside_back_cover_combo,
            "calendar-index",
        )
        self._set_combo_template(
            self._back_cover_combo,
            "geographic-word-cloud",
        )

        self._month_dividers_checkbox.setChecked(True)
        self._year_dividers_checkbox.setChecked(True)

        self._set_combo_template(
            self._photo_page_combo,
            "photo-page-2",
        )

        self._set_placement(
            self._month_placement_combo,
            DividerPlacement.RIGHT_PAGE,
        )
        self._set_placement(
            self._year_placement_combo,
            DividerPlacement.RIGHT_PAGE,
        )

    def set_available_years(
        self,
        years: set[int],
    ) -> None:
        available = len(years) > 1

        self._year_dividers_checkbox.setEnabled(
            available
        )

        if available:
            self._year_divider_hint.setText(
                f"{len(years)} years detected."
            )
        elif years:
            year = next(iter(years))
            self._year_divider_hint.setText(
                f"Year separators are unavailable: "
                f"all photos belong to {year}."
            )
        else:
            self._year_divider_hint.setText(
                "Year separators are unavailable until "
                "dated photos are present."
            )

        self._update_divider_controls()

    def settings(self) -> AlbumStructureSettings:
        return AlbumStructureSettings(
            covers={
                CoverPosition.FRONT: CoverSettings(
                    position=CoverPosition.FRONT,
                    template_id=self._template_id(
                        self._front_cover_combo
                    ),
                ),
                CoverPosition.INSIDE_FRONT: CoverSettings(
                    position=CoverPosition.INSIDE_FRONT,
                    template_id=self._template_id(
                        self._inside_front_cover_combo
                    ),
                ),
                CoverPosition.INSIDE_BACK: CoverSettings(
                    position=CoverPosition.INSIDE_BACK,
                    template_id=self._template_id(
                        self._inside_back_cover_combo
                    ),
                ),
                CoverPosition.BACK: CoverSettings(
                    position=CoverPosition.BACK,
                    template_id=self._template_id(
                        self._back_cover_combo
                    ),
                ),
            },
            month_dividers=DividerSettings(
                enabled=(
                    self._month_dividers_checkbox.isChecked()
                ),
                template_id=self._template_id(
                    self._month_divider_combo
                ),
                placement=self._placement(
                    self._month_placement_combo
                ),
            ),
            year_dividers=DividerSettings(
                enabled=self._year_dividers_checkbox.isChecked(),
                template_id=self._template_id(
                    self._year_divider_combo
                ),
                placement=self._placement(
                    self._year_placement_combo
                ),
            ),
            photo_pages=PhotoPageSettings(
                template_id=self._template_id(
                    self._photo_page_combo
                ),
            ),
            front_matter=self._special_pages(
                self._front_matter_list
            ),
            back_matter=self._special_pages(
                self._back_matter_list
            ),
        )

    def set_settings(
        self,
        settings: AlbumStructureSettings,
    ) -> None:
        self._set_combo_template(
            self._front_cover_combo,
            settings.covers[
                CoverPosition.FRONT
            ].template_id,
        )

        self._set_combo_template(
            self._inside_front_cover_combo,
            settings.covers[
                CoverPosition.INSIDE_FRONT
            ].template_id,
        )

        self._set_combo_template(
            self._inside_back_cover_combo,
            settings.covers[
                CoverPosition.INSIDE_BACK
            ].template_id,
        )

        self._set_combo_template(
            self._back_cover_combo,
            settings.covers[
                CoverPosition.BACK
            ].template_id,
        )

        self._month_dividers_checkbox.setChecked(
            settings.month_dividers.enabled
        )
        self._set_combo_template(
            self._month_divider_combo,
            settings.month_dividers.template_id,
        )
        self._set_placement(
            self._month_placement_combo,
            settings.month_dividers.placement,
        )

        self._year_dividers_checkbox.setChecked(
            settings.year_dividers.enabled
        )
        self._set_combo_template(
            self._year_divider_combo,
            settings.year_dividers.template_id,
        )
        self._set_placement(
            self._year_placement_combo,
            settings.year_dividers.placement,
        )

        self._set_combo_template(
            self._photo_page_combo,
            settings.photo_pages.template_id,
        )

        self._set_special_pages(
            self._front_matter_list,
            settings.front_matter,
        )
        self._set_special_pages(
            self._back_matter_list,
            settings.back_matter,
        )

        self._update_divider_controls()

    def _update_divider_controls(self) -> None:
        month_enabled = (
            self._month_dividers_checkbox.isChecked()
        )

        self._month_divider_combo.setEnabled(
            month_enabled
        )
        self._month_placement_combo.setEnabled(
            month_enabled
        )

        year_enabled = (
            self._year_dividers_checkbox.isEnabled()
            and self._year_dividers_checkbox.isChecked()
        )

        self._year_divider_combo.setEnabled(
            year_enabled
        )
        self._year_placement_combo.setEnabled(
            year_enabled
        )

    def _add_special_page(
        self,
        list_widget: QListWidget,
        combo: QComboBox,
    ) -> None:
        template_id = self._template_id(combo)

        template = self._registry.get(template_id)

        item = QListWidgetItem(template.name)
        item.setData(
            Qt.ItemDataRole.UserRole,
            template_id,
        )

        list_widget.addItem(item)

    @staticmethod
    def _remove_special_page(
        list_widget: QListWidget,
    ) -> None:
        row = list_widget.currentRow()

        if row >= 0:
            list_widget.takeItem(row)

    @staticmethod
    def _move_special_page(
        list_widget: QListWidget,
        offset: int,
    ) -> None:
        row = list_widget.currentRow()

        if row < 0:
            return

        target = row + offset

        if not 0 <= target < list_widget.count():
            return

        item = list_widget.takeItem(row)
        list_widget.insertItem(target, item)
        list_widget.setCurrentRow(target)

    def _set_special_pages(
        self,
        list_widget: QListWidget,
        pages: list[SpecialPage],
    ) -> None:
        list_widget.clear()

        for page in pages:
            template = self._registry.get(
                page.template_id
            )

            item = QListWidgetItem(
                template.name
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                page.template_id,
            )

            list_widget.addItem(item)

    @staticmethod
    def _special_pages(
        list_widget: QListWidget,
    ) -> list[SpecialPage]:
        return [
            SpecialPage(
                template_id=list_widget.item(index).data(
                    Qt.ItemDataRole.UserRole
                )
            )
            for index in range(list_widget.count())
        ]

    @staticmethod
    def _template_id(
        combo: QComboBox,
    ) -> str:
        return str(combo.currentData())

    @staticmethod
    def _placement(
        combo: QComboBox,
    ) -> DividerPlacement:
        return DividerPlacement(
            str(combo.currentData())
        )

    @staticmethod
    def _set_combo_template(
        combo: QComboBox,
        template_id: str,
    ) -> None:
        index = combo.findData(template_id)

        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _set_placement(
        combo: QComboBox,
        placement: DividerPlacement,
    ) -> None:
        index = combo.findData(
            placement.value
        )

        if index >= 0:
            combo.setCurrentIndex(index)

