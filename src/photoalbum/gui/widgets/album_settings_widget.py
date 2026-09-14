from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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

from photoalbum.i18n import Translator

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

    settings_changed = Signal()

    def __init__(
        self,
        registry: TemplateRegistry,
        translator: Translator | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._registry = registry
        self._translator = translator or Translator("en")
        self._loading_settings = False

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
                title=self._translator.tr("album.front_matter"),
                list_widget_name="_front_matter_list",
                combo_name="_front_matter_combo",
            )
        )

        special_layout.addWidget(
            self._create_special_pages_group(
                title=self._translator.tr("album.back_matter"),
                list_widget_name="_back_matter_list",
                combo_name="_back_matter_combo",
            )
        )

        layout.addLayout(special_layout)
        self._connect_settings_signals()
        layout.addStretch()

    def _connect_settings_signals(self) -> None:
        combos = [
            self._front_cover_combo,
            self._inside_front_cover_combo,
            self._inside_back_cover_combo,
            self._back_cover_combo,
            self._month_divider_combo,
            self._month_placement_combo,
            self._year_divider_combo,
            self._year_placement_combo,
            self._photo_page_combo,
        ]

        for combo in combos:
            combo.currentIndexChanged.connect(
                self._emit_settings_changed
            )

        self._month_dividers_checkbox.toggled.connect(
            self._emit_settings_changed
        )
        self._year_dividers_checkbox.toggled.connect(
            self._emit_settings_changed
        )

    def _emit_settings_changed(
        self,
        *args,
    ) -> None:
        if self._loading_settings:
            return

        self.settings_changed.emit()

    def _create_covers_group(self) -> QGroupBox:
        group = QGroupBox(self._translator.tr("album.covers"))
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
            self._translator.tr("album.front_cover"),
            self._front_cover_combo,
        )
        form.addRow(
            self._translator.tr("album.inside_front_cover"),
            self._inside_front_cover_combo,
        )
        form.addRow(
            self._translator.tr("album.inside_back_cover"),
            self._inside_back_cover_combo,
        )
        form.addRow(
            self._translator.tr("album.back_cover"),
            self._back_cover_combo,
        )

        return group

    def _create_dividers_group(self) -> QGroupBox:
        group = QGroupBox(self._translator.tr("album.dividers"))
        layout = QVBoxLayout(group)

        month_layout = QHBoxLayout()

        self._month_dividers_checkbox = QCheckBox(
            self._translator.tr("album.month_separators")
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
            self._translator.tr("album.year_separators")
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
        group = QGroupBox(self._translator.tr("album.photo_pages"))
        form = QFormLayout(group)

        self._photo_page_combo = self._create_template_combo(
            TemplateKind.PHOTO_PAGE
        )

        form.addRow(
            self._translator.tr("album.template"),
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

        add_button = QPushButton(self._translator.tr("album.add"))
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

        up_button = QPushButton(self._translator.tr("album.up"))
        down_button = QPushButton(self._translator.tr("album.down"))
        remove_button = QPushButton(self._translator.tr("album.remove"))

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

    def _template_display_name(self, template) -> str:
        key = f"template.{template.template_id}"
        translated = self._translator.tr(key)

        if translated == key:
            return template.name

        return translated

    def _create_template_combo(
        self,
        kind: TemplateKind,
    ) -> QComboBox:
        combo = QComboBox()

        for template in self._registry.list_by_kind(kind):
            combo.addItem(
                self._template_display_name(template),
                template.template_id,
            )

        return combo

    def _create_placement_combo(self) -> QComboBox:
        combo = QComboBox()

        combo.addItem(
            self._translator.tr("album.placement.natural"),
            DividerPlacement.NATURAL.value,
        )
        combo.addItem(
            self._translator.tr("album.placement.right"),
            DividerPlacement.RIGHT_PAGE.value,
        )
        combo.addItem(
            self._translator.tr("album.placement.right_blank"),
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
                self._translator.tr(
                    "album.years_detected",
                    count=len(years),
                )
            )
        elif years:
            year = next(iter(years))
            self._year_divider_hint.setText(
                self._translator.tr(
                    "album.year_unavailable",
                    year=year,
                )
            )
        else:
            self._year_divider_hint.setText(
                self._translator.tr(
                    "album.year_no_photos"
                )
            )

        self._update_divider_controls()

    def reset_to_defaults(self) -> None:
        self._loading_settings = True

        try:
            self._front_matter_list.clear()
            self._back_matter_list.clear()

            self._apply_defaults()
            self._update_divider_controls()

        finally:
            self._loading_settings = False


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
        self._loading_settings = True

        try:
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

        finally:
            self._loading_settings = False

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

        item = QListWidgetItem(
            self._template_display_name(template)
        )
        item.setData(
            Qt.ItemDataRole.UserRole,
            template_id,
        )

        list_widget.addItem(item)
        self._emit_settings_changed()

    def _remove_special_page(
        self,
        list_widget: QListWidget,
    ) -> None:
        row = list_widget.currentRow()

        if row >= 0:
            list_widget.takeItem(row)
            self._emit_settings_changed()

    def _move_special_page(
        self,
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

        self._emit_settings_changed()

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

