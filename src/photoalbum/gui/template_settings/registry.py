from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from photoalbum.album import PageInstance
from photoalbum.i18n import Translator

from .base import PageTemplateSettingsWidget
from .calendar_index import (
    CalendarIndexSettingsWidget,
)
from .geographic_word_cloud import (
    GeographicWordCloudSettingsWidget,
)
from .year_photo_scatter import (
    YearPhotoScatterSettingsWidget,
)


EditorFactory = Callable[
    [
        PageInstance,
        object,
    ],
    PageTemplateSettingsWidget,
]


class TemplateSettingsEditorRegistry:
    """
    GUI-side registry of template settings editors.

    PageInstanceDialog never contains template IDs.
    """

    def __init__(
        self,
    ) -> None:
        self._editors: dict[
            str,
            type[
                PageTemplateSettingsWidget
            ],
        ] = {}

    def register(
        self,
        template_id: str,
        editor_type: type[
            PageTemplateSettingsWidget
        ],
    ) -> None:
        self._editors[
            template_id
        ] = editor_type

    def editor_type(
        self,
        template_id: str,
    ) -> type[
        PageTemplateSettingsWidget
    ] | None:
        return self._editors.get(
            template_id
        )

    def create(
        self,
        template_id: str,
        instance: PageInstance,
        photos,
        *,
        translator: Translator,
        render_service=None,
        parent: QWidget | None = None,
    ) -> PageTemplateSettingsWidget | None:
        editor_type = self.editor_type(
            template_id
        )

        if editor_type is None:
            return None

        return editor_type(
            instance,
            photos,
            translator=translator,
            render_service=render_service,
            parent=parent,
        )


_registry = TemplateSettingsEditorRegistry()


def register_template_settings_editor(
    template_id: str,
    editor_type: type[
        PageTemplateSettingsWidget
    ],
) -> None:
    """
    Public extension hook.

    A future external template can register its editor without
    modifying PageInstanceDialog.
    """

    _registry.register(
        template_id,
        editor_type,
    )


def create_template_settings_editor(
    template_id: str,
    instance: PageInstance,
    photos,
    *,
    translator: Translator,
    render_service=None,
    parent: QWidget | None = None,
) -> PageTemplateSettingsWidget | None:
    return _registry.create(
        template_id,
        instance,
        photos,
        translator=translator,
        render_service=render_service,
        parent=parent,
    )


# Built-in template editors.
register_template_settings_editor(
    "year-photo-scatter",
    YearPhotoScatterSettingsWidget,
)

register_template_settings_editor(
    "geographic-word-cloud",
    GeographicWordCloudSettingsWidget,
)


register_template_settings_editor(
    "calendar-index",
    CalendarIndexSettingsWidget,
)
