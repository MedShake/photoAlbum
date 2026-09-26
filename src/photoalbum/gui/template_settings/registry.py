from __future__ import annotations

from PySide6.QtWidgets import QWidget

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.i18n import Translator
from photoalbum.template_engine import (
    template_extension_registry,
    translator_for_template,
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
    template_pack_settings=None,
    usage: str | None = None,
    temporal_context=(),
    preview_page=None,
    album_pages=None,
    parent: QWidget | None = None,
) -> PageTemplateSettingsWidget | None:
    editor_type = (
        template_extension_registry
        .settings_editor_type(
            template_id
        )
    )

    if editor_type is None:
        return None

    kwargs = {
        "translator": translator_for_template(
            template_id, translator
        ),
        "render_service": render_service,
        "page_format": page_format,
        "parent": parent,
    }

    # Optional opaque project/template-pack context.
    # Editors that do not depend on a pack remain completely
    # unaware of it.
    from inspect import signature

    parameters = signature(
        editor_type.__init__
    ).parameters

    if "template_pack_settings" in parameters:
        kwargs["template_pack_settings"] = (
            template_pack_settings
        )

    if "usage" in parameters:
        kwargs["usage"] = usage

    editor = editor_type(
        instance,
        photos,
        **kwargs,
    )

    if album_pages is not None:
        set_album_context = getattr(editor, "set_album_context", None)
        if set_album_context is not None:
            set_album_context(preview_page, album_pages)
    else:
        set_context = getattr(editor, "set_temporal_context", None)
        if set_context is not None:
            set_context(temporal_context)
    return editor
