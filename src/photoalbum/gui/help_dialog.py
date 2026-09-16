from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
)

from photoalbum.i18n import Translator


class HelpDialog(QDialog):
    """Display the localized Photo Album quick help."""

    def __init__(
        self,
        translator: Translator,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._translator = translator

        self.setWindowTitle(
            self._translator.tr("help.window_title")
        )
        self.resize(760, 680)
        self.setMinimumSize(600, 450)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            20,
            20,
            20,
            16,
        )
        layout.setSpacing(12)

        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(True)
        browser.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        browser.setHtml(
            self._translator.tr("help.content")
        )

        layout.addWidget(browser, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            parent=self,
        )
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)
