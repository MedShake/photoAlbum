from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.i18n import Translator


class PageTemplateSettingsWidget(QWidget):
    """
    Base class for one template's settings editor.

    A template editor owns every UI decision related to its
    PageInstance. PageInstanceDialog deliberately knows
    nothing about template-specific settings.
    """

    instance_changed = Signal()

    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator: Translator,
        render_service=None,
        page_format: PageFormat = A4,
        template_pack_settings=None,
        parent=None,
    ) -> None:
        super().__init__(parent)

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

    def instance(
        self,
    ) -> PageInstance:
        return self._instance

    def template_pack_settings(
        self,
    ) -> dict[str, object]:
        """
        Return a defensive copy of the template-pack context.

        Template editors may update pack-wide settings such as
        a shared theme. The dialog hosting the editor is
        responsible for propagating the resulting context back
        to its owner.
        """
        return dict(
            self._template_pack_settings
        )

    def set_template_pack_settings(
        self,
        settings,
    ) -> None:
        """
        Replace the editor's working template-pack context.

        Keep ownership local to the editor: callers and editors
        must not accidentally share a mutable settings dict.
        """
        self._template_pack_settings = dict(
            settings or {}
        )
