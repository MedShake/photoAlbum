from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout
from photoalbum.gui.template_settings.base import PageTemplateSettingsWidget

class BlankSettingsWidget(PageTemplateSettingsWidget):
    compact_dialog = True
    def __init__(self, instance, photos, *, translator, render_service=None, page_format=None, template_pack_settings=None, parent=None):
        super().__init__(instance, photos, translator=translator, render_service=render_service, page_format=page_format, template_pack_settings=template_pack_settings, parent=parent)
        layout = QVBoxLayout(self)
        label = QLabel(self._translator.tr("page_settings.blank_message"))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont(label.font()); font.setBold(True); font.setPointSize(font.pointSize() + 1)
        label.setFont(font)
        layout.addWidget(label)
