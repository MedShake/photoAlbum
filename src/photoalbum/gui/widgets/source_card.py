from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QComboBox, QPushButton

from photoalbum.sources import PhotoMetadataPolicy


class SourceCard(QWidget):
    enabled_changed = Signal(str, bool)
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    policy_changed = Signal(str, object)
    recursive_changed = Signal(str, bool)

    def __init__(self, source, available, translator, parent=None):
        super().__init__(parent)
        self.source = source
        tr = translator.tr
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        enabled = QCheckBox(tr("sources.active"))
        enabled.setChecked(source.enabled)
        enabled.toggled.connect(lambda value: self.enabled_changed.emit(source.id, value))
        heading.addWidget(enabled)
        provider_name = (
            tr("sources.local_folder")
            if source.kind == "local"
            else (source.provider_label or source.kind)
        )
        label = QLabel(f"{provider_name} — {source.collection_name}")
        label.setToolTip(str(source.config.get("directory") or source.config.get("base_url") or source.name))
        heading.addWidget(label)
        if source.kind == "local":
            heading.addSpacing(24)
            recursive = QCheckBox(tr("main.include_subdirectories"))
            recursive.setChecked(bool(source.config.get("recursive", False)))
            recursive.toggled.connect(
                lambda value: self.recursive_changed.emit(source.id, value)
            )
            heading.addWidget(recursive)
        heading.addStretch(1)
        for key, signal in (("sources.modify", self.edit_requested), ("sources.delete", self.delete_requested)):
            button = QPushButton(tr(key))
            button.clicked.connect(lambda _checked=False, s=signal: s.emit(source.id))
            heading.addWidget(button)
        layout.addLayout(heading)
        policy = source.effective_metadata_policy
        self._combos = {}
        row = QHBoxLayout()
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
