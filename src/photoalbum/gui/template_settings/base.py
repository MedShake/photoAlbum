from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from photoalbum.album import PageInstance
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
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._instance = instance
        self._photos = tuple(
            photos
        )
        self._translator = translator

    def instance(
        self,
    ) -> PageInstance:
        return self._instance
