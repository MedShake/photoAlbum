from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from photoalbum.album import PageInstance
from photoalbum.gui.template_settings import (
    create_template_settings_editor,
)
from photoalbum.i18n import Translator


class PageInstanceDialog(QDialog):
    """
    Generic host for a template-specific settings editor.

    No template-specific behaviour belongs here.
    """

    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator: Translator,
        parent=None,
    ) -> None:
        super().__init__(
            parent
        )

        self._instance = instance
        self._photos = tuple(
            photos
        )
        self._translator = translator

        self._editor = None

        self.setWindowTitle(
            self._translator.tr(
                "page_settings.title"
            )
        )

        self._create_content()

    def _template_name(
        self,
    ) -> str:
        key = (
            f"template."
            f"{self._instance.template_id}"
        )

        translated = self._translator.tr(
            key
        )

        if translated == key:
            return self._instance.template_id

        return translated

    def _create_content(
        self,
    ) -> None:
        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            self._template_name()
        )

        font = QFont(
            title.font()
        )

        font.setBold(
            True
        )

        title.setFont(
            font
        )

        layout.addWidget(
            title
        )

        self._editor = (
            create_template_settings_editor(
                self._instance.template_id,
                self._instance,
                self._photos,
                translator=self._translator,
                parent=self,
            )
        )

        if self._editor is None:
            no_settings = QLabel(
                self._translator.tr(
                    "page_settings.no_options"
                )
            )

            no_settings.setWordWrap(
                True
            )

            layout.addWidget(
                no_settings
            )

        else:
            layout.addWidget(
                self._editor
            )

        close_button = QPushButton(
            self._translator.tr(
                "page_settings.close"
            )
        )

        close_button.clicked.connect(
            self.accept
        )

        layout.addWidget(
            close_button,
            alignment=(
                Qt.AlignmentFlag.AlignRight
            ),
        )

    def instance(
        self,
    ) -> PageInstance:
        if self._editor is None:
            return self._instance

        return self._editor.instance()
