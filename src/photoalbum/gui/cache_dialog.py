from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLayout, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from photoalbum.cache_manager import CacheManager, GB
from photoalbum.gui.icon_resources import resource_icon


class CacheDialog(QDialog):
    def __init__(self, translator, parent=None, *, project_is_open=lambda: False, manager=None):
        super().__init__(parent)
        self._tr = translator.tr
        self._project_is_open = project_is_open
        self._manager = manager if manager is not None else CacheManager()
        self.setWindowTitle(self._tr("cache.title"))
        self.setMinimumSize(760, 460)
        self.resize(820, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.project_warning = QGroupBox()
        warning_layout = QHBoxLayout(self.project_warning)
        warning_layout.setContentsMargins(12, 8, 12, 8)
        warning_layout.setSpacing(8)
        self.project_warning_icon = QLabel()
        self.project_warning_icon.setFixedSize(18, 18)
        self.project_warning_icon.setPixmap(
            resource_icon("plan-warning-orange.svg").pixmap(QSize(16, 16))
        )
        warning_layout.addWidget(self.project_warning_icon)
        self.project_label = QLabel(self._tr("cache.close_project"))
        font = self.project_label.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.project_label.setFont(font)
        self.project_label.setWordWrap(True)
        warning_layout.addWidget(self.project_label, 1)
        layout.addWidget(self.project_warning)

        self.size_group = QGroupBox(self._tr("cache.size_management"))
        self.size_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        size_layout = QVBoxLayout(self.size_group)
        size_layout.setContentsMargins(14, 16, 14, 14)
        size_layout.setSpacing(10)
        size_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        size_explanation = QLabel(self._tr("cache.size_explanation"))
        size_explanation.setWordWrap(True)
        size_layout.addWidget(size_explanation)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(8)
        self.usage_label = QLabel()
        self.free_label = QLabel()
        form.addRow(self._tr("cache.used"), self.usage_label)
        form.addRow(self._tr("cache.free"), self.free_label)
        self.quota_spin = QDoubleSpinBox()
        self.quota_spin.setRange(0.01, 1_000_000_000)
        self.quota_spin.setDecimals(2)
        self.quota_spin.setSuffix(self._tr("cache.unit"))
        self.quota_spin.setMinimumWidth(180)
        self.quota_spin.setValue(self._manager.quota_gb)
        form.addRow(self._tr("cache.maximum"), self.quota_spin)
        self.unlimited_checkbox = QCheckBox(self._tr("cache.unlimited"))
        self.unlimited_checkbox.setChecked(self._manager.unlimited)
        form.addRow(self.unlimited_checkbox)
        # Keep the form at its natural height. Word-wrapped explanatory labels
        # must not be allowed to squeeze the controls on some Qt styles.
        form_widget.setMinimumHeight(form_widget.sizeHint().height())
        form_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        size_layout.addWidget(form_widget)
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        size_layout.addWidget(self.warning_label)
        self.size_group.setMinimumHeight(self.size_group.sizeHint().height())
        layout.addWidget(self.size_group)
        # QGroupBox titles are drawn on the top border. Keep an explicit gap
        # between sections so the next title never visually overlaps the
        # preceding group box on compact/native Qt styles.
        layout.addSpacing(16)

        self.cleanup_group = QGroupBox(self._tr("cache.cleanup"))
        self.cleanup_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        cleanup_layout = QVBoxLayout(self.cleanup_group)
        cleanup_layout.setContentsMargins(14, 16, 14, 14)
        cleanup_layout.setSpacing(10)
        cleanup_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        cleanup_explanation = QLabel(self._tr("cache.cleanup_explanation"))
        cleanup_explanation.setWordWrap(True)
        cleanup_layout.addWidget(cleanup_explanation)
        self.legacy_cleanup_checkbox = QCheckBox(self._tr("cache.legacy_cleanup_option"))
        self.legacy_cleanup_checkbox.setChecked(False)
        cleanup_layout.addWidget(self.legacy_cleanup_checkbox)
        self.legacy_cleanup_note = QLabel(self._tr("cache.legacy_cleanup_note"))
        self.legacy_cleanup_note.setWordWrap(True)
        note_font = self.legacy_cleanup_note.font()
        note_font.setItalic(True)
        note_font.setPointSize(max(8, note_font.pointSize() - 1))
        self.legacy_cleanup_note.setFont(note_font)
        note_layout = QHBoxLayout()
        note_layout.setContentsMargins(20, 0, 0, 0)
        note_layout.addWidget(self.legacy_cleanup_note, 1)
        cleanup_layout.addLayout(note_layout)
        self.purge_button = QPushButton(self._tr("cache.clear"))
        self.purge_button.clicked.connect(self._purge)
        cleanup_layout.addWidget(self.purge_button)
        self.cleanup_group.setMinimumHeight(self.cleanup_group.sizeHint().height())
        layout.addWidget(self.cleanup_group)
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
        self.legacy_cleanup_checkbox.setEnabled(not active)
        self.purge_button.setEnabled(not active)
        self.save_button.setEnabled(not active)
        self.project_warning.setVisible(active)
        self.project_label.setVisible(active)
        self.project_warning_icon.setVisible(active)
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
        legacy_caches = (
            self._manager.legacy_cache_directories()
            if self.legacy_cleanup_checkbox.isChecked()
            else []
        )
        message = self._tr("cache.confirm")
        if legacy_caches:
            legacy_size = self._manager.paths_size(legacy_caches) / GB
            key = "cache.legacy_found_one" if len(legacy_caches) == 1 else "cache.legacy_found_many"
            message += "\n\n" + self._tr(
                key, count=len(legacy_caches), value=f"{legacy_size:.2f}"
            )
        answer = QMessageBox.question(
            self, self.windowTitle(), message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes or self._project_is_open():
            return
        try:
            self._manager.purge()
            failures = self._manager.purge_legacy_caches(legacy_caches)
        except OSError:
            QMessageBox.warning(self, self.windowTitle(), self._tr("cache.error"))
        else:
            if failures:
                QMessageBox.warning(
                    self, self.windowTitle(),
                    self._tr("cache.legacy_cleanup_error", count=len(failures)),
                )
        self._refresh()
