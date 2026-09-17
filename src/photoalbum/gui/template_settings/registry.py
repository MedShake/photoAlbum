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
        "translator": translator,
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

    return editor_type(
        instance,
        photos,
        **kwargs,
    )
