from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.gui.template_settings import (
    create_template_settings_editor,
)
from photoalbum.i18n import Translator


class PageInstanceDialog(QDialog):
    THEME_REQUESTED = 2

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
        render_service=None,
        page_format: PageFormat = A4,
        template_pack_settings=None,
        usage: str | None = None,
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
        self._render_service = render_service
        self._page_format = page_format
        self._template_pack_settings = dict(
            template_pack_settings or {}
        )
        self._usage = usage

        self._editor = None

        self.setWindowTitle(
            self._translator.tr(
                "page_settings.title"
            )
        )

        self._create_content()
        self._set_initial_size()

    def _set_initial_size(
        self,
    ) -> None:
        if (
            self._editor is not None
            and getattr(self._editor, "compact_dialog", False)
        ):
            self.resize(420, 220)
            return

        target_width = 1100
        target_height = 720
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            target_width = min(target_width, round(available.width() * 0.90))
            target_height = min(target_height, round(available.height() * 0.90))
        self.resize(target_width, target_height)

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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            24,
            20,
            24,
            20,
        )
        layout.setSpacing(16)

        # ----------------------------------------------------
        # Template identity
        # ----------------------------------------------------

        title = QLabel(
            self._template_name()
        )

        font = QFont(
            title.font()
        )
        font.setBold(True)
        font.setPointSize(
            font.pointSize() + 2
        )
        title.setFont(font)

        layout.addWidget(title)

        description = QLabel(
            self._translator.tr(
                "page_settings.description"
            )
        )
        description.setWordWrap(True)
        description.setProperty(
            "secondary",
            True,
        )
        layout.addWidget(description)

        # ----------------------------------------------------
        # Template-owned settings editor
        # ----------------------------------------------------

        self._editor = (
            create_template_settings_editor(
                self._instance.template_id,
                self._instance,
                self._photos,
                translator=self._translator,
                render_service=self._render_service,
                page_format=self._page_format,
                template_pack_settings=(
                    self._template_pack_settings
                ),
                usage=self._usage,
                parent=self,
            )
        )

        if self._editor is None:
            no_settings = QLabel(
                self._translator.tr(
                    "page_settings.no_options"
                )
            )
            no_settings.setWordWrap(True)
            layout.addWidget(no_settings)

        else:
            self._editor.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            layout.addWidget(self._editor)

            theme_request = getattr(
                self._editor,
                "edit_theme_requested",
                None,
            )

            if theme_request is not None:
                theme_request.connect(
                    self._request_theme_editor
                )

        # ----------------------------------------------------
        # Footer
        # ----------------------------------------------------

        separator = QFrame()
        separator.setFrameShape(
            QFrame.Shape.HLine
        )
        separator.setFrameShadow(
            QFrame.Shadow.Sunken
        )
        layout.addWidget(separator)

        footer = QHBoxLayout()
        footer.addStretch()

        close_button = QPushButton(
            self._translator.tr(
                "page_settings.close"
            )
        )
        close_button.setDefault(True)
        close_button.clicked.connect(
            self.accept
        )

        footer.addWidget(close_button)
        layout.addLayout(footer)

    def _request_theme_editor(
        self,
    ) -> None:
        self.done(
            self.THEME_REQUESTED
        )

    def instance(
        self,
    ) -> PageInstance:
        if self._editor is None:
            return self._instance

        return self._editor.instance()

    def template_pack_settings(
        self,
    ) -> dict[str, object]:
        """
        Return the template-pack context produced by the editor.

        A template settings editor may change both its local
        PageInstance and pack-wide settings such as the shared
        MSB theme.
        """
        if self._editor is None:
            return dict(
                self._template_pack_settings
            )

        getter = getattr(
            self._editor,
            "template_pack_settings",
            None,
        )

        if getter is None:
            return dict(
                self._template_pack_settings
            )

        return dict(
            getter()
        )
