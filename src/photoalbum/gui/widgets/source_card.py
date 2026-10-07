from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout,
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

    def __init__(
        self,
        source,
        available,
        translator,
        parent=None,
        *,
        session_available: bool | None = None,
    ):
        provider_name = (
            translator.tr("sources.local_folder")
            if source.kind == "local"
            else (source.provider_label or source.kind)
        )
        super().__init__(f"{provider_name} — {source.collection_name}", parent)
        self.source = source
        tr = translator.tr
        self.setToolTip(
            str(source.config.get("directory") or source.config.get("base_url") or source.name)
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 7)
        layout.setSpacing(2)
        heading = QHBoxLayout()
        heading.setSpacing(6)
        enabled = QCheckBox(tr("sources.active"))
        enabled.setChecked(source.enabled)
        enabled.toggled.connect(lambda value: self.enabled_changed.emit(source.id, value))
        heading.addWidget(enabled)
        is_remote = source.kind != "local"
        reconnect_required = is_remote and session_available is False

        if source.kind == "local":
            heading.addSpacing(24)
            recursive = QCheckBox(tr("main.include_subdirectories"))
            recursive.setChecked(bool(source.config.get("recursive", False)))
            recursive.toggled.connect(
                lambda value: self.recursive_changed.emit(source.id, value)
            )
            heading.addWidget(recursive)

        self.connection_status_icon = QLabel()
        self.connection_status_icon.setFixedSize(16, 16)
        self.connection_status_icon.setVisible(reconnect_required)
        self.connection_status_label = QLabel(
            tr("sources.connection.reconnect_required") if reconnect_required else ""
        )
        self.connection_status_label.setVisible(reconnect_required)
        if reconnect_required:
            reconnect_tooltip = tr("sources.reconnect_required")
            self.connection_status_icon.setPixmap(
                resource_icon("plan-warning-orange.svg").pixmap(QSize(14, 14))
            )
            self.connection_status_icon.setToolTip(reconnect_tooltip)
            self.connection_status_label.setToolTip(reconnect_tooltip)
            heading.addWidget(self.connection_status_icon)
            heading.addWidget(self.connection_status_label)

        heading.addStretch(1)

        actions = QVBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(4)
        actions.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        action_width = 118

        self.sync_button = QPushButton(tr("sources.synchronize_one"))
        self.sync_button.setFixedWidth(action_width)
        self.sync_button.setEnabled(source.enabled and not reconnect_required)
        self.sync_button.clicked.connect(
            lambda _checked=False: self.sync_requested.emit(source.id)
        )
        actions.addWidget(self.sync_button, 0, Qt.AlignmentFlag.AlignRight)

        secondary_actions = QHBoxLayout()
        secondary_actions.setContentsMargins(0, 0, 0, 0)
        secondary_actions.setSpacing(4)

        self.edit_button = QPushButton(
            tr("sources.reconnect") if reconnect_required else tr("sources.modify")
        )
        self.edit_button.setFixedWidth(action_width)
        self.edit_button.clicked.connect(
            lambda _checked=False: self.edit_requested.emit(source.id)
        )
        secondary_actions.addWidget(self.edit_button)

        delete_button = QPushButton(tr("sources.delete"))
        delete_button.setFixedWidth(action_width)
        delete_button.clicked.connect(
            lambda _checked=False: self.delete_requested.emit(source.id)
        )
        secondary_actions.addWidget(delete_button)
        actions.addLayout(secondary_actions)

        heading.addLayout(actions)
        layout.addLayout(heading)
        policy = source.effective_metadata_policy
        self._combos = {}
        row = QHBoxLayout()
        row.setSpacing(5)
        labels = {"provider": source.provider_label or source.kind,
                  "exif": "EXIF", "filename": tr("photos.policy.filename"),
                  "geocoding": "Nominatim", "none": tr("photos.policy.none")}
        for field, preference, order in (
            ("date", policy.date_preference, ("provider", "exif", "filename")),
            ("gps", policy.gps_preference, ("provider", "exif")),
            ("location", policy.location_preference, ("provider", "geocoding", "none")),
        ):
            row.addWidget(QLabel(tr("photos.policy." + field)))
            combo = QComboBox()
            for key in order:
                if key in available.get(field, ()) or key == "none" or (key == "geocoding" and policy.nominatim_enabled):
                    combo.addItem(labels[key], "source" if key == "provider" else key)
            combo.setCurrentIndex(max(0, combo.findData(preference)))
            combo.setEnabled(combo.count() > 0)
            combo.currentIndexChanged.connect(self._emit_policy)
            self._combos[field] = combo
            row.addWidget(combo)
        self._nominatim = QCheckBox("Nominatim")
        self._nominatim.setToolTip(tr("photos.policy.nominatim_tooltip"))
        self._nominatim.setChecked(policy.nominatim_enabled)
        self._nominatim.toggled.connect(self._emit_policy)
        row.addWidget(self._nominatim)
        row.addStretch()
        layout.addLayout(row)

    def _emit_policy(self, *_args):
        old = self.source.effective_metadata_policy
        self.policy_changed.emit(self.source.id, PhotoMetadataPolicy(
            date_preference=self._combos["date"].currentData() or old.date_preference,
            gps_preference=self._combos["gps"].currentData() or old.gps_preference,
            location_preference=self._combos["location"].currentData() or old.location_preference,
            nominatim_enabled=self._nominatim.isChecked(),
        ))
