from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
)

from photoalbum.i18n import Translator
from photoalbum.template_engine import discover_template_packs


class TemplatePackHelpDialog(QDialog):
    """Display documentation supplied by installed template packs."""

    def __init__(
        self,
        translator: Translator,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._translator = translator
        self._packs = tuple(
            pack
            for pack in discover_template_packs()
            if pack.documentation_paths
        )

        self.setWindowTitle(
            self._translator.tr(
                "template_help.window_title"
            )
        )
        self.resize(1000, 720)
        self.setMinimumSize(720, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)

        if not self._packs:
            label = QLabel(
                self._translator.tr(
                    "template_help.no_documentation"
                )
            )
            label.setWordWrap(True)
            layout.addWidget(label, 1)
        else:
            splitter = QSplitter(
                Qt.Orientation.Horizontal,
                self,
            )

            self._pack_list = QListWidget(splitter)
            self._browser = QTextBrowser(splitter)
            self._browser.setOpenExternalLinks(True)
            self._browser.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
            self._browser.setFrameShape(
                QTextBrowser.Shape.NoFrame
            )

            for pack in self._packs:
                item = QListWidgetItem(pack.name)
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    pack.pack_id,
                )
                self._pack_list.addItem(item)

            splitter.addWidget(self._pack_list)
            splitter.addWidget(self._browser)
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            splitter.setSizes([220, 780])

            layout.addWidget(splitter, 1)

            self._pack_list.currentRowChanged.connect(
                self._show_pack
            )
            self._pack_list.setCurrentRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            parent=self,
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)




    def _show_pack(self, row: int) -> None:
        if row < 0 or row >= len(self._packs):
            self._browser.clear()
            return

        pack = self._packs[row]
        path = pack.documentation_path(
            self._translator.language
        )

        if path is None:
            self._browser.clear()
            return

        text = path.read_text(encoding="utf-8")

        self._browser.setHtml(text)

        # Relative links/images in the pack documentation are resolved
        # from the pack directory.
        self._browser.document().setBaseUrl(
            path.parent.as_uri() + "/"
        )
