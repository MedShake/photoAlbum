from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from photoalbum.cache_manager import CacheManager, GB


class CacheDialog(QDialog):
    def __init__(self, translator, parent=None, *, project_is_open=lambda: False, manager=None):
        super().__init__(parent)
        self._tr = translator.tr
        self._project_is_open = project_is_open
        self._manager = manager if manager is not None else CacheManager()
        self.setWindowTitle(self._tr("cache.title"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.usage_label = QLabel()
        self.free_label = QLabel()
        form.addRow(self._tr("cache.used"), self.usage_label)
        form.addRow(self._tr("cache.free"), self.free_label)
        self.quota_spin = QDoubleSpinBox()
        self.quota_spin.setRange(0.01, 1_000_000_000)
        self.quota_spin.setDecimals(2)
        self.quota_spin.setSuffix(self._tr("cache.unit"))
        self.quota_spin.setValue(self._manager.quota_gb)
        form.addRow(self._tr("cache.maximum"), self.quota_spin)
        self.unlimited_checkbox = QCheckBox(self._tr("cache.unlimited"))
        self.unlimited_checkbox.setChecked(self._manager.unlimited)
        form.addRow(self.unlimited_checkbox)
        layout.addLayout(form)
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)
        explanation = QLabel(self._tr("cache.explanation"))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.project_label = QLabel(self._tr("cache.close_project"))
        self.project_label.setWordWrap(True)
        layout.addWidget(self.project_label)
        self.purge_button = QPushButton(self._tr("cache.clear"))
        self.purge_button.clicked.connect(self._purge)
        layout.addWidget(self.purge_button)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText(self._tr("cache.save"))
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(self._tr("cache.close"))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.quota_spin.valueChanged.connect(self._update_controls)
        self.unlimited_checkbox.toggled.connect(self._update_controls)
        self._refresh()

    def _refresh(self):
        self.usage_label.setText(self._tr("cache.size", value=f"{self._manager.used_bytes() / GB:.2f}"))
        self.free_label.setText(self._tr("cache.size", value=f"{self._manager.available_bytes() / GB:.2f}"))
        self._update_controls()

    def _update_controls(self, *_args):
        active = self._project_is_open()
        unlimited = self.unlimited_checkbox.isChecked()
        self.quota_spin.setEnabled(not active and not unlimited)
        self.unlimited_checkbox.setEnabled(not active)
        self.purge_button.setEnabled(not active)
        self.save_button.setEnabled(not active)
        self.project_label.setVisible(active)
        exceeds = not unlimited and self.quota_spin.value() * GB > self._manager.available_bytes()
        self.warning_label.setText(self._tr("cache.space_warning") if exceeds else "")

    def _save(self):
        if self._project_is_open():
            return
        try:
            self._manager.configure(self.quota_spin.value(), self.unlimited_checkbox.isChecked())
        except OSError:
            QMessageBox.warning(self, self.windowTitle(), self._tr("cache.error"))
            return
        self.accept()

    def _purge(self):
        if self._project_is_open():
            return
        answer = QMessageBox.question(
            self, self.windowTitle(), self._tr("cache.confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes or self._project_is_open():
            return
        try:
            self._manager.purge()
        except OSError:
            QMessageBox.warning(self, self.windowTitle(), self._tr("cache.error"))
        self._refresh()
