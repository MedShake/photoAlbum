from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from photoalbum.gui.template_settings.base import (
    PageTemplateSettingsWidget,
)


class MsbTemplateSettingsWidget(
    PageTemplateSettingsWidget
):
    edit_theme_requested = Signal()

    """
    Base class for MSB template settings editors.

    Page-specific settings remain owned by PageInstance.
    Shared theme settings remain owned by the template-pack
    context and are propagated through PageInstanceDialog.
    """

    def create_section_title(
        self,
        text: str,
    ) -> QWidget:
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

    def create_page_settings_title(
        self,
    ) -> QWidget:
        return self.create_section_title(
            self._translator.tr(
                "page_settings.page_section"
            )
        )

    def create_no_page_settings_label(
        self,
    ) -> QLabel:
        label = QLabel(
            self._translator.tr(
                "page_settings.no_page_settings"
            )
        )
        label.setWordWrap(True)
        return label

    def create_preview_title(
        self,
    ) -> QWidget:
        return self.create_section_title(
            self._translator.tr(
                "page_settings.preview_section"
            )
        )

    def create_preview_label(
        self,
        width: int,
        height: int,
    ) -> QLabel:
        label = QLabel()
        label.setFixedSize(width, height)
        label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        label.setStyleSheet(
            "border: 1px solid #888;"
            "background: white;"
        )
        return label

    def create_msb_theme_group(
        self,
    ) -> QWidget:
        section = QWidget()

        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(
            self.create_section_title(
                self._translator.tr(
                    "page_settings.theme_section"
                )
            )
        )

        theme_name = self._translator.tr(
            "msb_theme.title"
        )

        explanation = QLabel(
            self._translator.tr(
                "page_settings.theme_explanation",
                theme_name=theme_name,
            )
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        button = QPushButton(
            self._translator.tr(
                "msb_theme.modify"
            )
        )
        button.clicked.connect(
            self._edit_msb_theme
        )

        button.setMaximumWidth(
            button.sizeHint().width() + 16
        )

        layout.addWidget(button)
        layout.addStretch()

        return section

    def _edit_msb_theme(
        self,
    ) -> None:
        self.edit_theme_requested.emit()

    def msb_theme_changed(
        self,
    ) -> None:
        pass
