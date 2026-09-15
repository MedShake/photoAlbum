from __future__ import annotations

from PySide6.QtWidgets import QWidget

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.i18n import Translator
from photoalbum.templates import (
    template_extension_registry,
)

from .base import PageTemplateSettingsWidget


def create_template_settings_editor(
    template_id: str,
    instance: PageInstance,
    photos,
    *,
    translator: Translator,
    render_service=None,
    page_format: PageFormat = A4,
    parent: QWidget | None = None,
) -> PageTemplateSettingsWidget | None:
    # Safe and idempotent: templates overwrite their own
    # registry entry rather than creating duplicates.
    from photoalbum.templates import (
        register_builtin_template_extensions,
    )

    register_builtin_template_extensions()

    editor_type = (
        template_extension_registry
        .settings_editor_type(
            template_id
        )
    )

    if editor_type is None:
        return None

    return editor_type(
        instance,
        photos,
        translator=translator,
        render_service=render_service,
        page_format=page_format,
        parent=parent,
    )
