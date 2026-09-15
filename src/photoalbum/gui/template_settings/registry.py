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


class TemplateSettingsEditorRegistry:
    """
    Compatibility facade over the generic template-extension
    registry.

    There is deliberately no second source of truth.
    """

    def register(
        self,
        template_id: str,
        editor_type,
    ) -> None:
        register_template_settings_editor(
            template_id,
            editor_type,
        )

    def editor_type(
        self,
        template_id: str,
    ):
        return (
            template_extension_registry
            .settings_editor_type(
                template_id
            )
        )

    def create(
        self,
        template_id: str,
        instance: PageInstance,
        photos,
        *,
        translator: Translator,
        render_service=None,
        page_format: PageFormat = A4,
        parent: QWidget | None = None,
    ) -> PageTemplateSettingsWidget | None:
        return create_template_settings_editor(
            template_id,
            instance,
            photos,
            translator=translator,
            render_service=render_service,
            page_format=page_format,
            parent=parent,
        )


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


def register_template_settings_editor(
    template_id: str,
    editor_type,
) -> None:
    """
    Compatibility API.

    New templates should register a PageTemplateExtension.
    """

    from photoalbum.templates.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )

    existing = (
        template_extension_registry.get(
            template_id
        )
    )

    register_template_extension(
        PageTemplateExtension(
            template_id=template_id,
            settings_editor_type=editor_type,
            preview_backend=(
                existing.preview_backend
                if existing is not None
                else None
            ),
            widget_renderer=(
                existing.widget_renderer
                if existing is not None
                else None
            ),
        )
    )
