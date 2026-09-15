from __future__ import annotations

import secrets

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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from photoalbum.templates.defaults import (
    DEFAULT_TEMPLATES,
)
from photoalbum.i18n import Translator
from photoalbum.gui.template_labels import template_display_name
from photoalbum.gui.page_instance_dialog import PageInstanceDialog

from photoalbum.album import (
    page_format_from_id,
    AlbumStructureSettings,
    CoverPosition,
    CoverScatterSettings,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PageInstance,
    PageNumberSettings,
    PageOrientation,
    PhotoCaptionSettings,
    PhotoPageSettings,
    PrintSettings,
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
        render_service=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._render_service = render_service

        self._registry = registry
        self._translator = translator or Translator("en")
        self._loading_settings = False

        self._cover_instances: dict[
            CoverPosition,
            PageInstance,
        ] = {}

        self._month_divider_instance: PageInstance | None = None
        self._year_divider_instance: PageInstance | None = None

        self._year_dividers_available = False

        self._photo_provider = None

        self._create_content()
        self._apply_defaults()
        self.set_available_years(set())

    def set_photo_provider(
        self,
        provider,
    ) -> None:
        self._photo_provider = provider

    def _create_content(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(
            self._create_page_format_group()
        )
        layout.addWidget(self._create_covers_group())
        layout.addWidget(self._create_dividers_group())
        layout.addWidget(self._create_photo_pages_group())
        layout.addWidget(self._create_page_numbers_group())
        layout.addWidget(self._create_print_group())

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
            self._page_format_combo,
            self._orientation_combo,
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

        self._caption_datetime_checkbox.toggled.connect(
            self._emit_settings_changed
        )
        self._caption_location_checkbox.toggled.connect(
            self._emit_settings_changed
        )
        self._page_numbers_checkbox.toggled.connect(
            self._emit_settings_changed
        )

        self._page_multiple_4_checkbox.toggled.connect(
            self._emit_settings_changed
        )

    def _emit_settings_changed(
        self,
        *args,
    ) -> None:
        if self._loading_settings:
            return

        self.settings_changed.emit()

    def _create_page_format_group(self) -> QGroupBox:
        group = QGroupBox(
            self._translator.tr(
                "album.page_format"
            )
        )

        form = QFormLayout(group)

        self._page_format_combo = QComboBox()

        self._page_format_combo.addItem(
            "A4 — 210 × 297 mm",
            "a4",
        )
        self._page_format_combo.addItem(
            self._translator.tr(
                "album.paper_format_a5_development"
            ),
            "a5",
        )
        self._page_format_combo.addItem(
            "US Letter — 215,9 × 279,4 mm",
            "us-letter",
        )

        # A5 remains part of the project model but is not
        # selectable in V1. Some templates still require
        # format-specific adaptation for this smaller page.
        page_format_model = (
            self._page_format_combo.model()
        )

        a5_index = (
            self._page_format_combo.findData(
                "a5"
            )
        )

        if a5_index >= 0:
            a5_item = page_format_model.item(
                a5_index
            )

            if a5_item is not None:
                a5_item.setEnabled(
                    False
                )

        form.addRow(
            self._translator.tr(
                "album.paper_format"
            ),
            self._page_format_combo,
        )

        self._orientation_combo = QComboBox()

        self._orientation_combo.addItem(
            self._translator.tr(
                "album.orientation_portrait"
            ),
            PageOrientation.PORTRAIT.value,
        )

        self._orientation_combo.addItem(
            self._translator.tr(
                "album.orientation_landscape_development"
            ),
            PageOrientation.LANDSCAPE.value,
        )

        # Landscape is deliberately visible but unavailable
        # until every page template supports it correctly.
        model = self._orientation_combo.model()
        landscape_item = model.item(1)

        if landscape_item is not None:
            landscape_item.setEnabled(False)

        form.addRow(
            self._translator.tr(
                "album.orientation"
            ),
            self._orientation_combo,
        )

        return group

    def _create_covers_group(self) -> QGroupBox:
        group = QGroupBox(
            self._translator.tr(
                "album.covers"
            )
        )

        form = QFormLayout(group)

        rows = [
            (
                CoverPosition.FRONT,
                "album.front_cover",
                "_front_cover_combo",
            ),
            (
                CoverPosition.INSIDE_FRONT,
                "album.inside_front_cover",
                "_inside_front_cover_combo",
            ),
            (
                CoverPosition.INSIDE_BACK,
                "album.inside_back_cover",
                "_inside_back_cover_combo",
            ),
            (
                CoverPosition.BACK,
                "album.back_cover",
                "_back_cover_combo",
            ),
        ]

        for (
            position,
            label_key,
            attribute_name,
        ) in rows:
            combo = self._create_template_combo(
                TemplateKind.COVER
            )

            setattr(
                self,
                attribute_name,
                combo,
            )

            container = QWidget()
            row_layout = QHBoxLayout(
                container
            )
            row_layout.setContentsMargins(
                0,
                0,
                0,
                0,
            )

            row_layout.addWidget(
                combo,
                1,
            )

            settings_button = QPushButton(
                self._translator.tr(
                    "album.settings"
                )
            )

            settings_button.clicked.connect(
                lambda checked=False,
                pos=position,
                cb=combo:
                self._configure_cover_instance(
                    pos,
                    cb,
                )
            )

            row_layout.addWidget(
                settings_button
            )

            form.addRow(
                self._translator.tr(
                    label_key
                ),
                container,
            )

        return group

    def _cover_instance(
        self,
        position: CoverPosition,
        combo: QComboBox,
    ) -> PageInstance:
        template_id = self._template_id(
            combo
        )

        instance = self._cover_instances.get(
            position
        )

        if (
            instance is None
            or instance.template_id
            != template_id
        ):
            instance = PageInstance(
                template_id=template_id,
            )

            self._cover_instances[
                position
            ] = instance

        return instance

    def _configure_cover_instance(
        self,
        position: CoverPosition,
        combo: QComboBox,
    ) -> None:
        instance = self._cover_instance(
            position,
            combo,
        )

        photos = (
            self._photo_provider()
            if self._photo_provider
            else []
        )

        dialog = PageInstanceDialog(
            instance,
            photos,
            translator=self._translator,
            render_service=self._render_service,
            page_format=page_format_from_id(
                str(
                    self._page_format_combo.currentData()
                )
            ),
            parent=self,
        )

        if dialog.exec():
            self._cover_instances[
                position
            ] = dialog.instance()

            self._emit_settings_changed()


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

        self._month_divider_settings_button = QPushButton(
            self._translator.tr(
                "album.settings"
            )
        )

        self._month_divider_settings_button.clicked.connect(
            lambda checked=False:
            self._configure_divider_instance(
                "month"
            )
        )

        month_layout.addWidget(
            self._month_divider_settings_button
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

        self._year_divider_settings_button = QPushButton(
            self._translator.tr(
                "album.settings"
            )
        )

        self._year_divider_settings_button.clicked.connect(
            lambda checked=False:
            self._configure_divider_instance(
                "year"
            )
        )

        year_layout.addWidget(
            self._year_divider_settings_button
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

    def _configure_divider_instance(
        self,
        kind: str,
    ) -> None:
        if kind == "month":
            combo = self._month_divider_combo
            instance = self._month_divider_instance
        elif kind == "year":
            combo = self._year_divider_combo
            instance = self._year_divider_instance
        else:
            raise ValueError(
                f"Unknown divider kind: {kind}"
            )

        template_id = self._template_id(
            combo
        )

        if (
            instance is None
            or instance.template_id != template_id
        ):
            instance = PageInstance(
                template_id=template_id
            )

        photos = (
            self._photo_provider()
            if self._photo_provider is not None
            else []
        )

        dialog = PageInstanceDialog(
            instance,
            photos,
            translator=self._translator,
            render_service=self._render_service,
            page_format=page_format_from_id(
                str(
                    self._page_format_combo.currentData()
                )
            ),
            parent=self,
        )

        if not dialog.exec():
            return

        instance = dialog.instance()

        if kind == "month":
            self._month_divider_instance = instance
        else:
            self._year_divider_instance = instance

        self._emit_settings_changed()

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

        self._caption_datetime_checkbox = QCheckBox(
            self._translator.tr("album.caption_datetime")
        )
        self._caption_location_checkbox = QCheckBox(
            self._translator.tr("album.caption_location")
        )

        form.addRow(
            "",
            self._caption_datetime_checkbox,
        )
        form.addRow(
            "",
            self._caption_location_checkbox,
        )

        return group

    def _create_page_numbers_group(self) -> QGroupBox:
        group = QGroupBox(
            self._translator.tr("album.page_numbering")
        )
        layout = QVBoxLayout(group)

        self._page_numbers_checkbox = QCheckBox(
            self._translator.tr("album.show_page_numbers")
        )

        layout.addWidget(self._page_numbers_checkbox)

        return group

    def _create_print_group(self) -> QGroupBox:
        group = QGroupBox(
            self._translator.tr("album.printing")
        )

        layout = QVBoxLayout(group)

        self._page_multiple_4_checkbox = QCheckBox(
            self._translator.tr(
                "album.page_multiple_4"
            )
        )

        layout.addWidget(
            self._page_multiple_4_checkbox
        )

        return group

    def _create_special_pages_group(
        self,
        *,
        title: str,
        list_widget_name: str,
        combo_name: str,
    ) -> QGroupBox:
        group = QGroupBox(
            title
        )

        layout = QVBoxLayout(
            group
        )

        list_widget = QListWidget()

        setattr(
            self,
            list_widget_name,
            list_widget,
        )

        layout.addWidget(
            list_widget
        )

        combo = self._create_template_combo(
            TemplateKind.SPECIAL_PAGE
        )

        setattr(
            self,
            combo_name,
            combo,
        )

        add_layout = QHBoxLayout()

        add_layout.addWidget(
            combo,
            1,
        )

        add_button = QPushButton(
            self._translator.tr(
                "album.add"
            )
        )

        add_button.clicked.connect(
            lambda checked=False,
            lw=list_widget,
            cb=combo:
            self._add_special_page(
                lw,
                cb,
            )
        )

        add_layout.addWidget(
            add_button
        )

        layout.addLayout(
            add_layout
        )

        # These actions concern the selected row as a whole.
        controls = QHBoxLayout()

        up_button = QPushButton(
            self._translator.tr(
                "album.up"
            )
        )

        down_button = QPushButton(
            self._translator.tr(
                "album.down"
            )
        )

        remove_button = QPushButton(
            self._translator.tr(
                "album.remove"
            )
        )

        up_button.clicked.connect(
            lambda checked=False,
            lw=list_widget:
            self._move_special_page(
                lw,
                -1,
            )
        )

        down_button.clicked.connect(
            lambda checked=False,
            lw=list_widget:
            self._move_special_page(
                lw,
                1,
            )
        )

        remove_button.clicked.connect(
            lambda checked=False,
            lw=list_widget:
            self._remove_special_page(
                lw
            )
        )

        controls.addWidget(
            up_button
        )
        controls.addWidget(
            down_button
        )
        controls.addWidget(
            remove_button
        )

        controls.addStretch()

        layout.addLayout(
            controls
        )

        return group

    def _template_display_name(self, template) -> str:
        return template_display_name(
            template,
            self._translator,
        )

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

        self._caption_datetime_checkbox.setChecked(True)
        self._caption_location_checkbox.setChecked(True)
        self._page_numbers_checkbox.setChecked(True)
        self._page_multiple_4_checkbox.setChecked(False)

        self._set_combo_template(
            self._front_cover_combo,
            DEFAULT_TEMPLATES.front_cover,
        )
        self._set_combo_template(
            self._inside_front_cover_combo,
            DEFAULT_TEMPLATES.inside_front_cover,
        )
        self._set_combo_template(
            self._inside_back_cover_combo,
            DEFAULT_TEMPLATES.inside_back_cover,
        )
        self._set_combo_template(
            self._back_cover_combo,
            DEFAULT_TEMPLATES.back_cover,
        )

        self._month_dividers_checkbox.setChecked(True)
        self._year_dividers_checkbox.setChecked(True)

        self._set_combo_template(
            self._photo_page_combo,
            DEFAULT_TEMPLATES.photo_page,
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
        self._year_dividers_available = (
            len(years) > 1
        )

        self._year_dividers_checkbox.setEnabled(
            self._year_dividers_available
        )

        if self._year_dividers_available:
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
        # A new project must never inherit instance-specific
        # state (scatter seeds/history, template options...).
        self._cover_instances.clear()

        self._front_matter_list.clear()
        self._back_matter_list.clear()

        self._loading_settings = True

        try:
            self._front_matter_list.clear()
            self._back_matter_list.clear()

            self._apply_defaults()
            self._update_divider_controls()

        finally:
            self._loading_settings = False


    def _divider_instance(
        self,
        current: PageInstance | None,
        combo: QComboBox,
    ) -> PageInstance:
        template_id = self._template_id(
            combo
        )

        if (
            current is not None
            and current.template_id == template_id
        ):
            return current

        return PageInstance(
            template_id=template_id,
        )

    def settings(self) -> AlbumStructureSettings:
        return AlbumStructureSettings(
            page_format=str(
                self._page_format_combo.currentData()
            ),
            orientation=PageOrientation(
                self._orientation_combo.currentData()
            ),
            covers={
                position: CoverSettings(
                    position=position,
                    page=self._cover_instance(
                        position,
                        combo,
                    ),
                )
                for position, combo in (
                    (
                        CoverPosition.FRONT,
                        self._front_cover_combo,
                    ),
                    (
                        CoverPosition.INSIDE_FRONT,
                        self._inside_front_cover_combo,
                    ),
                    (
                        CoverPosition.INSIDE_BACK,
                        self._inside_back_cover_combo,
                    ),
                    (
                        CoverPosition.BACK,
                        self._back_cover_combo,
                    ),
                )
            },
            month_dividers=DividerSettings(
                enabled=(
                    self._month_dividers_checkbox.isChecked()
                ),
                page=self._divider_instance(
                    self._month_divider_instance,
                    self._month_divider_combo,
                ),
                placement=self._placement(
                    self._month_placement_combo
                ),
            ),
            year_dividers=DividerSettings(
                enabled=self._year_dividers_checkbox.isChecked(),
                page=self._divider_instance(
                    self._year_divider_instance,
                    self._year_divider_combo,
                ),
                placement=self._placement(
                    self._year_placement_combo
                ),
            ),
            photo_pages=PhotoPageSettings(
                template_id=self._template_id(
                    self._photo_page_combo
                ),
                caption=PhotoCaptionSettings(
                    show_datetime=(
                        self._caption_datetime_checkbox.isChecked()
                    ),
                    show_location=(
                        self._caption_location_checkbox.isChecked()
                    ),
                ),
            ),
            page_numbers=PageNumberSettings(
                enabled=self._page_numbers_checkbox.isChecked(),
            ),
            print_settings=PrintSettings(
                page_multiple=(
                    4
                    if self._page_multiple_4_checkbox.isChecked()
                    else None
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
            page_format_index = (
                self._page_format_combo.findData(
                    settings.page_format
                )
            )

            if page_format_index >= 0:
                self._page_format_combo.setCurrentIndex(
                    page_format_index
                )

            orientation_index = (
                self._orientation_combo.findData(
                    settings.orientation.value
                )
            )

            if orientation_index >= 0:
                self._orientation_combo.setCurrentIndex(
                    orientation_index
                )

            self._set_combo_template(
                self._front_cover_combo,
                settings.covers[
                    CoverPosition.FRONT
                ].template_id,
            )

            self._cover_instances = {
                position: cover.page
                for position, cover
                in settings.covers.items()
            }

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

            self._month_divider_instance = (
                settings.month_dividers.page
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

            self._year_divider_instance = (
                settings.year_dividers.page
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

            self._caption_datetime_checkbox.setChecked(
                settings.photo_pages.caption.show_datetime
            )
            self._caption_location_checkbox.setChecked(
                settings.photo_pages.caption.show_location
            )
            self._page_numbers_checkbox.setChecked(
                settings.page_numbers.enabled
            )

            self._page_multiple_4_checkbox.setChecked(
                settings.print_settings.page_multiple == 4
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
        self._month_divider_settings_button.setEnabled(
            month_enabled
        )
        self._month_placement_combo.setEnabled(
            month_enabled
        )

        year_enabled = (
            self._year_dividers_available
            and self._year_dividers_checkbox.isChecked()
        )

        self._year_divider_combo.setEnabled(
            year_enabled
        )
        self._year_divider_settings_button.setEnabled(
            year_enabled
        )
        self._year_placement_combo.setEnabled(
            year_enabled
        )

    def _install_special_page_row_widget(
        self,
        list_widget: QListWidget,
        item: QListWidgetItem,
        page: PageInstance,
    ) -> None:
        template = self._registry.get(
            page.template_id
        )

        row_widget = QWidget(
            list_widget
        )

        row_layout = QHBoxLayout(
            row_widget
        )

        row_layout.setContentsMargins(
            6,
            2,
            2,
            2,
        )

        row_layout.setSpacing(
            8
        )

        label = QLabel(
            self._template_display_name(
                template
            )
        )

        row_layout.addWidget(
            label,
            1,
        )

        settings_button = QPushButton(
            self._translator.tr(
                "album.settings"
            )
        )

        settings_button.clicked.connect(
            lambda checked=False,
            lw=list_widget,
            current_item=item:
            self._configure_special_page_item(
                lw,
                current_item,
            )
        )

        row_layout.addWidget(
            settings_button
        )

        item.setSizeHint(
            row_widget.sizeHint()
        )

        list_widget.setItemWidget(
            item,
            row_widget,
        )

    def _configure_special_page_item(
        self,
        list_widget: QListWidget,
        item: QListWidgetItem,
    ) -> None:
        value = item.data(
            Qt.ItemDataRole.UserRole
        )

        if isinstance(
            value,
            str,
        ):
            value = PageInstance(
                template_id=value
            )

            item.setData(
                Qt.ItemDataRole.UserRole,
                value,
            )

        if not isinstance(
            value,
            PageInstance,
        ):
            return

        photos = (
            self._photo_provider()
            if self._photo_provider is not None
            else []
        )

        dialog = PageInstanceDialog(
            value,
            photos,
            translator=self._translator,
            render_service=self._render_service,
            page_format=page_format_from_id(
                str(
                    self._page_format_combo.currentData()
                )
            ),
            parent=self,
        )

        if not dialog.exec():
            return

        updated = dialog.instance()

        item.setData(
            Qt.ItemDataRole.UserRole,
            updated,
        )

        self._install_special_page_row_widget(
            list_widget,
            item,
            updated,
        )

        self._emit_settings_changed()

    def _add_special_page(
        self,
        list_widget: QListWidget,
        combo: QComboBox,
    ) -> None:
        template_id = self._template_id(
            combo
        )

        instance = PageInstance(
            template_id=template_id
        )

        item = QListWidgetItem()

        item.setData(
            Qt.ItemDataRole.UserRole,
            instance,
        )

        list_widget.addItem(
            item
        )

        self._install_special_page_row_widget(
            list_widget,
            item,
            instance,
        )

        list_widget.setCurrentItem(
            item
        )

        self._emit_settings_changed()

    def _configure_special_page(
        self,
        list_widget: QListWidget,
    ) -> None:
        item = list_widget.currentItem()

        if item is None:
            return

        self._configure_special_page_item(
            list_widget,
            item,
        )

    def _remove_special_page(
        self,
        list_widget: QListWidget,
    ) -> None:
        row = list_widget.currentRow()

        if row < 0:
            return

        item = list_widget.takeItem(
            row
        )

        del item

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

        item = list_widget.takeItem(
            row
        )

        page = item.data(
            Qt.ItemDataRole.UserRole
        )

        list_widget.insertItem(
            target,
            item,
        )

        if isinstance(
            page,
            PageInstance,
        ):
            self._install_special_page_row_widget(
                list_widget,
                item,
                page,
            )

        list_widget.setCurrentRow(
            target
        )

        self._emit_settings_changed()

    def _set_special_pages(
        self,
        list_widget: QListWidget,
        pages: list[PageInstance],
    ) -> None:
        list_widget.clear()

        for page in pages:
            item = QListWidgetItem()

            item.setData(
                Qt.ItemDataRole.UserRole,
                page,
            )

            list_widget.addItem(
                item
            )

            self._install_special_page_row_widget(
                list_widget,
                item,
                page,
            )

    def _special_pages(
        self,
        list_widget: QListWidget,
    ) -> list[PageInstance]:
        pages: list[
            PageInstance
        ] = []

        for index in range(
            list_widget.count()
        ):
            value = list_widget.item(
                index
            ).data(
                Qt.ItemDataRole.UserRole
            )

            if isinstance(
                value,
                PageInstance,
            ):
                pages.append(
                    value
                )
                continue

            # Defensive repair for list items created by the
            # previous development version during this session.
            if isinstance(
                value,
                str,
            ):
                instance = PageInstance(
                    template_id=value
                )

                list_widget.item(
                    index
                ).setData(
                    Qt.ItemDataRole.UserRole,
                    instance,
                )

                pages.append(
                    instance
                )
                continue

            raise TypeError(
                "Special page does not contain "
                "a PageInstance."
            )

        return pages

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

