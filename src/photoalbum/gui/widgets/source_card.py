from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QToolButton, QVBoxLayout, QWidget, QGridLayout, QSizePolicy,
)

from photoalbum.gui.icon_resources import resource_icon
from photoalbum.sources import PhotoMetadataPolicy


class SourceCard(QGroupBox):
    enabled_changed = Signal(str, bool)
    sync_requested = Signal(str)
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    policy_changed = Signal(str, object)
    recursive_changed = Signal(str, bool)
    expansion_requested = Signal(str, bool)

    def __init__(
        self,
        source,
        available,
        translator,
        parent=None,
        *,
        session_available: bool | None = None,
        status: str | None = None,
    ):
        super().__init__(parent)
        self.source = source
        self._translator = translator
        self._expanded = True
        tr = translator.tr
        provider_name = (
            tr("sources.local_folder")
            if source.kind == "local"
            else (source.provider_label or source.kind)
        )
        self._display_name = f"{provider_name} — {source.collection_name}"
        self.setToolTip(
            str(source.config.get("directory") or source.config.get("base_url") or source.name)
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 6)
        layout.setSpacing(3)

        # Always-visible accordion header: source identity + active state + warning.
        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(6)

        self.expand_button = QToolButton()
        self.expand_button.setAutoRaise(True)
        self.expand_button.setArrowType(Qt.ArrowType.DownArrow)
        self.expand_button.setToolTip(self._display_name)
        self.expand_button.clicked.connect(
            lambda _checked=False: self.expansion_requested.emit(
                source.id, not self._expanded
            )
        )
        heading.addWidget(self.expand_button)

        self.title_label = QLabel(self._display_name)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.title_label.setMinimumWidth(0)
        self.title_label.setToolTip(self._display_name)
        heading.addWidget(self.title_label, 1)

        enabled = QCheckBox(tr("sources.active"))
        enabled.setChecked(source.enabled)
        enabled.toggled.connect(lambda value: self.enabled_changed.emit(source.id, value))
        heading.addWidget(enabled)

        is_remote = source.kind != "local"
        reconnect_required = is_remote and session_available is False
        status = status or ("no_session" if reconnect_required else None)
        self.connection_status_icon = QLabel()
        self.connection_status_icon.setFixedSize(16, 16)
        self.connection_status_icon.setVisible(status is not None)
        self.connection_status_label = QLabel(
            tr("sources.state." + status) if status else ""
        )
        self.connection_status_label.setVisible(status is not None)
        if status:
            reconnect_tooltip = (
                tr("sources.state.missing_images_hint")
                if status == "disconnected_missing_images"
                else (tr("sources.state.cached_hint") if is_remote else tr("sources.state.snapshot_hint"))
            )
            severe = status == "disconnected_missing_images"
            self.connection_status_icon.setPixmap(
                resource_icon(
                    "plan-warning-red.svg" if severe else "plan-warning-orange.svg"
                ).pixmap(QSize(14, 14))
            )
            self.connection_status_label.setStyleSheet(
                "color: #c62828;" if severe else "color: #ef6c00;"
            )
            self.connection_status_icon.setToolTip(reconnect_tooltip)
            self.connection_status_label.setToolTip(reconnect_tooltip)
            heading.addWidget(self.connection_status_icon)
            heading.addWidget(self.connection_status_label)

        heading.addStretch(1)
        layout.addLayout(heading)

        # Two rows rather than one oversized row: policies then actions.
        # This prevents Windows font/DPI metrics from imposing an enormous
        # minimum width on the main application window.
        self.details_widget = QWidget(self)
        details = QVBoxLayout(self.details_widget)
        details.setContentsMargins(24, 0, 0, 0)
        details.setSpacing(5)
        options = QGridLayout()
        options.setContentsMargins(0, 0, 0, 0)
        options.setHorizontalSpacing(8)
        options.setVerticalSpacing(3)

        if source.kind == "local":
            recursive = QCheckBox(tr("main.include_subdirectories"))
            recursive.setChecked(bool(source.config.get("recursive", False)))
            recursive.toggled.connect(
                lambda value: self.recursive_changed.emit(source.id, value)
            )
            details.addWidget(recursive)

        policy = source.effective_metadata_policy
        self._combos = {}
        labels = {
            "provider": source.provider_label or source.kind,
            "exif": "EXIF",
            "filename": tr("photos.policy.filename"),
            "geocoding": "Nominatim",
            "none": tr("photos.policy.none"),
        }
        for column, (field, preference, order) in enumerate((
            ("date", policy.date_preference, ("provider", "exif", "filename")),
            ("gps", policy.gps_preference, ("provider", "exif")),
            ("location", policy.location_preference, ("provider", "geocoding", "none")),
        )):
            options.addWidget(QLabel(tr("photos.policy." + field)), 0, column)
            combo = QComboBox()
            for key in order:
                if (
                    key in available.get(field, ())
                    or key == "none"
                    or (key == "geocoding" and policy.nominatim_enabled)
                ):
                    combo.addItem(labels[key], "source" if key == "provider" else key)
            combo.setCurrentIndex(max(0, combo.findData(preference)))
            combo.setEnabled(combo.count() > 0)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            combo.currentIndexChanged.connect(self._emit_policy)
            self._combos[field] = combo
            options.addWidget(combo, 1, column)
            options.setColumnStretch(column, 1)

        self._nominatim = QCheckBox("Nominatim")
        self._nominatim.setToolTip(tr("photos.policy.nominatim_tooltip"))
        self._nominatim.setChecked(policy.nominatim_enabled)
        self._nominatim.toggled.connect(self._emit_policy)
        options.addWidget(self._nominatim, 1, 3)
        details.addLayout(options)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        actions.addStretch(1)

        self.sync_button = QPushButton(tr("sources.synchronize_one"))
        self.sync_button.setEnabled(source.enabled and not reconnect_required)
        self.sync_button.clicked.connect(
            lambda _checked=False: self.sync_requested.emit(source.id)
        )
        actions.addWidget(self.sync_button)

        self.edit_button = QPushButton(
            tr("sources.reconnect") if reconnect_required else tr("sources.modify")
        )
        self.edit_button.clicked.connect(
            lambda _checked=False: self.edit_requested.emit(source.id)
        )
        actions.addWidget(self.edit_button)

        self.delete_button = QPushButton(tr("sources.delete"))
        self.delete_button.clicked.connect(
            lambda _checked=False: self.delete_requested.emit(source.id)
        )
        actions.addWidget(self.delete_button)
        details.addLayout(actions)

        layout.addWidget(self.details_widget)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.details_widget.setVisible(self._expanded)
        self.expand_button.setArrowType(
            Qt.ArrowType.DownArrow if self._expanded else Qt.ArrowType.RightArrow
        )

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def _emit_policy(self, *_args):
        old = self.source.effective_metadata_policy
        self.policy_changed.emit(self.source.id, PhotoMetadataPolicy(
            date_preference=self._combos["date"].currentData() or old.date_preference,
            gps_preference=self._combos["gps"].currentData() or old.gps_preference,
            location_preference=self._combos["location"].currentData() or old.location_preference,
            nominatim_enabled=self._nominatim.isChecked(),
        ))
