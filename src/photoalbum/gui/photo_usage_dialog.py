from PySide6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QDialogButtonBox
from photoalbum.models import PhotoUsage


class PhotoUsageDialog(QDialog):
    def __init__(self, photo, translator, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translator.tr("photos.usage.title"))
        layout = QVBoxLayout(self)
        self._choices = {}
        for usage in PhotoUsage:
            radio = QRadioButton(translator.tr("photos.usage." + usage.value))
            radio.setChecked(photo.usage == usage)
            self._choices[usage] = radio
            layout.addWidget(radio)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def usage(self):
        return next(usage for usage, button in self._choices.items() if button.isChecked())
