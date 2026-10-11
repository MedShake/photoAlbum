from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from photoalbum.gui.template_settings.base import PageTemplateSettingsWidget


class ComplexTemplateSettingsWidget(PageTemplateSettingsWidget):
    def create_section_title(self, text: str) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title = QLabel(text)
        font = QFont(title.font())
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        return section

    def create_page_settings_title(self) -> QWidget:
        return self.create_section_title(self._translator.tr("page_settings.page_section"))
