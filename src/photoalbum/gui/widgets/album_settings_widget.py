from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from photoalbum.template_engine.defaults import (
    default_template_choices,
)
from photoalbum.i18n import Translator
from photoalbum.gui.template_labels import template_display_name
from photoalbum.gui.page_instance_dialog import PageInstanceDialog
from photoalbum.template_engine.discovery import pack_settings_editor
from photoalbum.template_engine.instances import create_template_instance
from photoalbum.album import (
    PAGE_FORMATS,
    PageFormat,
    page_format_from_id,
    oriented_page_format,
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PageInstance,
    PageNumberSettings,
    PageOrientation,
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
        self._default_templates = default_template_choices(registry)
        self._translator = translator or Translator("en")
        self._loading_settings = False

        self._template_pack_settings: dict[str, object] = {}

        self._cover_instances: dict[
            CoverPosition,
            PageInstance,
        ] = {}

        self._month_divider_instance: PageInstance | None = None
        self._year_divider_instance: PageInstance | None = None
        self._photo_page_instance: PageInstance | None = None

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
        # Page format and orientation are deliberately excluded here.
        #
        # A physical target change refreshes all compatible template
        # choices through _refresh_template_choices(), which emits one
        # consolidated settings_changed signal when the refresh is
        # complete. Connecting them here as well would rebuild the album
        # once before/alongside that refresh.
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

        for format_id, page_format in PAGE_FORMATS.items():
            self._page_format_combo.addItem(
                (
                    f"{page_format.name} — "
                    f"{page_format.width_mm:g} × "
                    f"{page_format.height_mm:g} mm"
                ),
                format_id,
            )

        self._page_format_combo.addItem(self._translator.tr("album.custom_format"), "custom")
        self._custom_dimensions = (210.0, 297.0)
        self._custom_format_controls = QWidget()
        custom_form = QHBoxLayout(self._custom_format_controls)
        custom_form.setContentsMargins(0, 0, 0, 0)
        self._custom_width_spin = QDoubleSpinBox()
        self._custom_height_spin = QDoubleSpinBox()
        for spin, value in zip((self._custom_width_spin, self._custom_height_spin), self._custom_dimensions):
            spin.setRange(50.0, 2000.0)
            spin.setDecimals(2)
            spin.setSuffix(" mm")
            spin.setValue(value)
        for key, spin in (("album.custom_width", self._custom_width_spin),
                          ("album.custom_height", self._custom_height_spin)):
            label = QLabel(self._translator.tr(key))
            label.setBuddy(spin)
            custom_form.addWidget(label)
            custom_form.addWidget(spin)
        self._custom_apply_button = QPushButton(self._translator.tr("album.apply_format"))
        self._custom_apply_button.clicked.connect(self._apply_custom_format)
        custom_form.addWidget(self._custom_apply_button)
        custom_form.addStretch()

        self._orientation_combo = QComboBox()
        self._orientation_combo.addItem(
            self._translator.tr(
                "album.orientation_portrait"
            ),
            PageOrientation.PORTRAIT.value,
        )
        self._orientation_combo.addItem(
            self._translator.tr(
                "album.orientation_landscape"
            ),
            PageOrientation.LANDSCAPE.value,
        )

        self._page_format_combo.currentIndexChanged.connect(
            self._refresh_format_availability
        )
        self._orientation_combo.currentIndexChanged.connect(
            self._refresh_template_choices
        )

        form.addRow(
            self._translator.tr(
                "album.page_format"
            ),
            self._page_format_combo,
        )
        form.addRow(
            self._translator.tr(
                "album.orientation"
            ),
            self._orientation_combo,
        )

        form.addRow(self._custom_format_controls)
        self._refresh_format_availability()

        return group

    def _page_geometry(
        self,
        format_id: str | None = None,
        orientation: PageOrientation | None = None,
    ) -> tuple[float, float]:
        if format_id is None:
            format_id = str(
                self._page_format_combo.currentData()
            )

        if orientation is None:
            orientation = PageOrientation(
                self._orientation_combo.currentData()
            )

        if format_id == "custom":
            return self._custom_dimensions
        page = oriented_page_format(page_format_from_id(format_id), orientation)
        return page.width_mm, page.height_mm

    def _format_has_available_orientation(
        self,
        format_id: str,
    ) -> bool:
        return any(
            self._registry.album_page_available(
                *self._page_geometry(
                    format_id=format_id,
                    orientation=orientation,
                )
            )
            for orientation in PageOrientation
        )

    def _apply_custom_format(self) -> None:
        dimensions = (self._custom_width_spin.value(), self._custom_height_spin.value())
        if dimensions != self._custom_dimensions:
            self._custom_dimensions = dimensions
            self._refresh_orientation_availability()

    def _refresh_format_availability(self) -> None:
        model = self._page_format_combo.model()

        for index in range(
            self._page_format_combo.count()
        ):
            format_id = str(
                self._page_format_combo.itemData(index)
            )
            item = model.item(index)

            if item is None:
                continue

            available = (
                self._format_has_available_orientation(
                    format_id
                )
            )

            item.setEnabled(available)

            if format_id == "custom":
                item.setEnabled(True)
                continue

            page_format = PAGE_FORMATS[format_id]
            base = (
                f"{page_format.name} — "
                f"{page_format.width_mm:g} × "
                f"{page_format.height_mm:g} mm"
            )

            if available:
                item.setText(base)
                item.setToolTip("")
            else:
                item.setText(
                    base
                    + " — "
                    + self._translator.tr(
                        "album.templates_unavailable_format"
                    )
                )
                item.setToolTip(
                    self._translator.tr(
                        "album.templates_unavailable_format"
                    )
                )

        self._refresh_orientation_availability()

    def _refresh_orientation_availability(self) -> None:
        format_id = str(
            self._page_format_combo.currentData()
        )

        custom = format_id == "custom"
        self._custom_format_controls.setVisible(custom)
        self._orientation_combo.setEnabled(not custom)
        if custom:
            with QSignalBlocker(self._orientation_combo):
                orientation = "landscape" if self._custom_dimensions[0] > self._custom_dimensions[1] else "portrait"
                self._orientation_combo.setCurrentIndex(self._orientation_combo.findData(orientation))
            self._refresh_template_choices()
            return

        model = self._orientation_combo.model()

        for index in range(
            self._orientation_combo.count()
        ):
            value = self._orientation_combo.itemData(
                index
            )
            orientation = PageOrientation(value)
            item = model.item(index)

            if item is None:
                continue

            available = (
                self._registry.album_page_available(
                    *self._page_geometry(
                        format_id=format_id,
                        orientation=orientation,
                    )
                )
            )

            item.setEnabled(available)

            if orientation == PageOrientation.PORTRAIT:
                base = self._translator.tr(
                    "album.orientation_portrait"
                )
            else:
                base = self._translator.tr(
                    "album.orientation_landscape"
                )

            if available:
                item.setText(base)
                item.setToolTip("")
            else:
                item.setText(
                    base
                    + " — "
                    + self._translator.tr(
                        "album.templates_unavailable_orientation"
                    )
                )
                item.setToolTip(
                    self._translator.tr(
                        "album.templates_unavailable_orientation"
                    )
                )

        current = model.item(self._orientation_combo.currentIndex())
        if current is None or not current.isEnabled():
            # A format may support only one orientation. Choose a valid target
            # before repopulating templates, without starting a second refresh.
            with QSignalBlocker(self._orientation_combo):
                for index in range(self._orientation_combo.count()):
                    item = model.item(index)
                    if item is not None and item.isEnabled():
                        self._orientation_combo.setCurrentIndex(index)
                        break

        self._refresh_template_choices()

    def _refresh_template_choices(self) -> None:
        """
        Refresh template choices after a physical target change.

        Keep an existing selection when it is still compatible with
        the new target. Cover selectors are additionally filtered by
        their physical cover position.
        """
        if not hasattr(
            self,
            "_photo_page_combo",
        ):
            return

        combos = (
            (
                self._front_cover_combo,
                TemplateKind.COVER,
                CoverPosition.FRONT,
            ),
            (
                self._inside_front_cover_combo,
                TemplateKind.COVER,
                CoverPosition.INSIDE_FRONT,
            ),
            (
                self._inside_back_cover_combo,
                TemplateKind.COVER,
                CoverPosition.INSIDE_BACK,
            ),
            (
                self._back_cover_combo,
                TemplateKind.COVER,
                CoverPosition.BACK,
            ),
            (
                self._month_divider_combo,
                TemplateKind.MONTH_DIVIDER,
                None,
            ),
            (
                self._year_divider_combo,
                TemplateKind.YEAR_DIVIDER,
                None,
            ),
            (
                self._photo_page_combo,
                TemplateKind.PHOTO_PAGE,
                None,
            ),
            (
                self._front_matter_combo,
                TemplateKind.SPECIAL_PAGE,
                None,
            ),
            (
                self._back_matter_combo,
                TemplateKind.SPECIAL_PAGE,
                None,
            ),
        )

        # Repopulating the selectors changes their current indexes.
        # Those index changes must not each be interpreted as a user
        # settings change: a physical target change is one transaction
        # and must cause one album rebuild.
        was_loading = self._loading_settings
        self._loading_settings = True

        try:
            for combo, kind, cover_position in combos:
                selected = combo.currentData()

                self._populate_template_combo(
                    combo,
                    kind,
                    cover_position=cover_position,
                )

                if selected is not None:
                    index = combo.findData(selected)

                    if index >= 0:
                        combo.setCurrentIndex(index)
            for list_widget in (self._front_matter_list, self._back_matter_list):
                for index in range(list_widget.count()):
                    item = list_widget.item(index)
                    page = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(page, PageInstance):
                        self._install_special_page_row_widget(list_widget, item, page)
        finally:
            self._loading_settings = was_loading

        # During load_settings(), the surrounding load operation owns
        # notification. For an actual user target change, emit exactly
        # once after every selector is coherent with the new target.
        if not was_loading:
            self.settings_changed.emit()


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
                TemplateKind.COVER,
                cover_position=position,
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
            instance = create_template_instance(
                template_id=template_id,
            )

            self._cover_instances[
                position
            ] = instance

        return instance

    def _open_pack_settings_dialog(self, template_id: str) -> bool:
        definition = self._registry.get(template_id)
        if definition.pack_id is None:
            return False
        editor = pack_settings_editor(definition.pack_id)
        if editor is None:
            return False
        updated = editor(
            self._template_pack_settings,
            translator=self._translator,
            parent=self,
        )
        if updated is None:
            return False
        self._template_pack_settings = updated
        return True

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
            page_format=self._oriented_page_format(),
            template_pack_settings=(
                self._template_pack_settings
            ),
            parent=self,
        )

        result = dialog.exec()

        if not result:
            return

        self._cover_instances[
            position
        ] = dialog.instance()

        self._template_pack_settings = (
            dialog.template_pack_settings()
        )

        if (
            result
            == PageInstanceDialog.THEME_REQUESTED
        ):
            if self._open_pack_settings_dialog(dialog.instance().template_id):
                self._emit_settings_changed()
            return

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
            instance = create_template_instance(
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
            page_format=self._oriented_page_format(),
            template_pack_settings=(
                self._template_pack_settings
            ),
            usage=(
                "year_divider"
                if kind == "year"
                else "month_divider"
            ),
            parent=self,
        )

        result = dialog.exec()

        if not result:
            return

        instance = dialog.instance()

        self._template_pack_settings = (
            dialog.template_pack_settings()
        )

        if kind == "month":
            self._month_divider_instance = instance
        else:
            self._year_divider_instance = instance

        if (
            result
            == PageInstanceDialog.THEME_REQUESTED
        ):
            if self._open_pack_settings_dialog(dialog.instance().template_id):
                self._emit_settings_changed()
            return

        self._emit_settings_changed()

    def _create_photo_pages_group(self) -> QGroupBox:
        group = QGroupBox(self._translator.tr("album.photo_pages"))
        form = QFormLayout(group)

        self._photo_page_combo = self._create_template_combo(
            TemplateKind.PHOTO_PAGE
        )

        template_container = QWidget()
        template_layout = QHBoxLayout(
            template_container
        )
        template_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        template_layout.addWidget(
            self._photo_page_combo,
            1,
        )

        self._photo_page_settings_button = QPushButton(
            self._translator.tr(
                "album.settings"
            )
        )

        self._photo_page_settings_button.clicked.connect(
            lambda checked=False:
            self._configure_photo_page_instance()
        )

        template_layout.addWidget(
            self._photo_page_settings_button
        )

        form.addRow(
            self._translator.tr("album.template"),
            template_container,
        )

        return group

    def _photo_instance(
        self,
    ) -> PageInstance:
        template_id = self._template_id(
            self._photo_page_combo
        )

        if (
            self._photo_page_instance is None
            or self._photo_page_instance.template_id
            != template_id
        ):
            self._photo_page_instance = create_template_instance(
                template_id=template_id
            )

        return self._photo_page_instance

    def _configure_photo_page_instance(
        self,
    ) -> None:
        instance = self._photo_instance()

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
            page_format=self._oriented_page_format(),
            template_pack_settings=(
                self._template_pack_settings
            ),
            parent=self,
        )

        result = dialog.exec()

        if not result:
            return

        self._photo_page_instance = (
            dialog.instance()
        )

        self._template_pack_settings = (
            dialog.template_pack_settings()
        )

        if (
            result
            == PageInstanceDialog.THEME_REQUESTED
        ):
            if self._open_pack_settings_dialog(dialog.instance().template_id):
                self._emit_settings_changed()
            return

        self._emit_settings_changed()

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

    def _template_available_for_selection(
        self,
        template,
        *,
        cover_position: CoverPosition | None = None,
    ) -> bool:
        if not template.is_compatible_with_page(*self._page_geometry()):
            return False

        if (
            cover_position is not None
            and not template.supports_cover_position(
                cover_position
            )
        ):
            return False

        return True

    def _populate_template_combo(
        self,
        combo: QComboBox,
        kind: TemplateKind,
        *,
        cover_position: CoverPosition | None = None,
    ) -> None:
        combo.blockSignals(True)

        try:
            combo.clear()

            for template in self._registry.list_by_kind(kind):
                if not self._template_available_for_selection(
                    template,
                    cover_position=cover_position,
                ):
                    continue

                combo.addItem(
                    self._template_display_name(template),
                    template.template_id,
                )
        finally:
            combo.blockSignals(False)

    def _create_template_combo(
        self,
        kind: TemplateKind,
        *,
        cover_position: CoverPosition | None = None,
    ) -> QComboBox:
        combo = QComboBox()

        self._populate_template_combo(
            combo,
            kind,
            cover_position=cover_position,
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

        self._page_numbers_checkbox.setChecked(True)
        self._page_multiple_4_checkbox.setChecked(False)

        self._set_combo_template(
            self._front_cover_combo,
            self._default_templates.front_cover,
        )
        self._set_combo_template(
            self._inside_front_cover_combo,
            self._default_templates.inside_front_cover,
        )
        self._set_combo_template(
            self._inside_back_cover_combo,
            self._default_templates.inside_back_cover,
        )
        self._set_combo_template(
            self._back_cover_combo,
            self._default_templates.back_cover,
        )

        self._month_dividers_checkbox.setChecked(True)
        self._year_dividers_checkbox.setChecked(True)

        self._set_combo_template(
            self._photo_page_combo,
            self._default_templates.photo_page,
        )
        self._set_combo_template(
            self._year_divider_combo,
            self._default_templates.year_divider,
        )
        self._set_combo_template(
            self._month_divider_combo,
            self._default_templates.month_divider,
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
        self._year_dividers_available = bool(years)

        self._year_dividers_checkbox.setEnabled(
            self._year_dividers_available
        )

        if self._year_dividers_available:
            count = len(years)
            self._year_divider_hint.setText(
                self._translator.tr(
                    (
                        "album.year_detected"
                        if count == 1
                        else "album.years_detected"
                    ),
                    count=count,
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
        # template-owned state.
        self._cover_instances.clear()
        self._photo_page_instance = None

        self._front_matter_list.clear()
        self._back_matter_list.clear()

        self._loading_settings = True

        self._template_pack_settings = {}

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

        return create_template_instance(
            template_id=template_id,
        )

    def _oriented_page_format(self):
        width, height = self._page_geometry()
        format_id = str(self._page_format_combo.currentData())
        name = "Custom" if format_id == "custom" else PAGE_FORMATS[format_id].name
        return PageFormat(name, width, height)

    def settings(self) -> AlbumStructureSettings:
        # Keep replacement instances stable across persistence and rebuilding.
        self._month_divider_instance = self._divider_instance(
            self._month_divider_instance, self._month_divider_combo,
        )
        self._year_divider_instance = self._divider_instance(
            self._year_divider_instance, self._year_divider_combo,
        )
        return AlbumStructureSettings(
            custom_width_mm=self._custom_dimensions[0],
            custom_height_mm=self._custom_dimensions[1],
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
                page=self._month_divider_instance,
                placement=self._placement(
                    self._month_placement_combo
                ),
            ),
            year_dividers=DividerSettings(
                enabled=self._year_dividers_checkbox.isChecked(),
                page=self._year_divider_instance,
                placement=self._placement(
                    self._year_placement_combo
                ),
            ),
            photo_pages=PhotoPageSettings(
                page=self._photo_instance(),
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
            template_pack_settings=dict(
                self._template_pack_settings
            ),
        )

    def set_settings(
        self,
        settings: AlbumStructureSettings,
    ) -> None:
        self._loading_settings = True

        self._template_pack_settings = dict(
            settings.template_pack_settings
        )

        try:
            self._custom_dimensions = (settings.custom_width_mm, settings.custom_height_mm)
            for spin, value in zip((self._custom_width_spin, self._custom_height_spin), self._custom_dimensions):
                spin.setValue(value)
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

            self._refresh_orientation_availability()

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

            self._photo_page_instance = (
                settings.photo_pages.page
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

        compatible = template.is_compatible_with_page(*self._page_geometry())
        settings_button.setEnabled(compatible)
        if not compatible:
            warning = self._translator.tr("album.special_page_incompatible")
            label.setText(f"⚠ {label.text()} — {warning}")
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            row_widget.setToolTip(warning)

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
            value = create_template_instance(
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

        if not self._registry.get(value.template_id).is_compatible_with_page(*self._page_geometry()):
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
            page_format=self._oriented_page_format(),
            template_pack_settings=(
                self._template_pack_settings
            ),
            parent=self,
        )

        result = dialog.exec()

        if not result:
            return

        updated = dialog.instance()

        self._template_pack_settings = (
            dialog.template_pack_settings()
        )

        item.setData(
            Qt.ItemDataRole.UserRole,
            updated,
        )

        self._install_special_page_row_widget(
            list_widget,
            item,
            updated,
        )

        if (
            result
            == PageInstanceDialog.THEME_REQUESTED
        ):
            if self._open_pack_settings_dialog(dialog.instance().template_id):
                self._emit_settings_changed()
            return

        self._emit_settings_changed()

    def _add_special_page(
        self,
        list_widget: QListWidget,
        combo: QComboBox,
    ) -> None:
        template_id = self._template_id(
            combo
        )

        instance = create_template_instance(
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
                instance = create_template_instance(
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
