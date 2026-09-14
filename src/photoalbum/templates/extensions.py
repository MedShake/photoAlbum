from __future__ import annotations

from dataclasses import dataclass

from photoalbum.templates.preview_backend import (
    TemplatePreviewBackend,
)


@dataclass(frozen=True)
class PageTemplateExtension:
    """
    Optional executable behaviour owned by a page template.

    The album/template registry still describes the template
    itself (name, supported page kinds, etc.).

    This extension describes executable behaviour:
    - settings editor
    - expensive/asynchronous preview backend
    - later: PDF renderer, validator, exporter...
    """

    template_id: str

    settings_editor_type: type | None = None
    preview_backend: TemplatePreviewBackend | None = None
    widget_renderer: object | None = None


class PageTemplateExtensionRegistry:
    def __init__(self) -> None:
        self._extensions: dict[
            str,
            PageTemplateExtension,
        ] = {}

    def register(
        self,
        extension: PageTemplateExtension,
    ) -> None:
        self._extensions[
            extension.template_id
        ] = extension

    def get(
        self,
        template_id: str,
    ) -> PageTemplateExtension | None:
        return self._extensions.get(
            template_id
        )

    def settings_editor_type(
        self,
        template_id: str,
    ):
        extension = self.get(
            template_id
        )

        if extension is None:
            return None

        return extension.settings_editor_type

    def widget_renderer(
        self,
        template_id: str,
    ):
        extension = self.get(
            template_id
        )

        if extension is None:
            return None

        return extension.widget_renderer

    def preview_backend(
        self,
        template_id: str,
    ) -> TemplatePreviewBackend | None:
        extension = self.get(
            template_id
        )

        if extension is None:
            return None

        return extension.preview_backend


template_extension_registry = (
    PageTemplateExtensionRegistry()
)


def register_template_extension(
    extension: PageTemplateExtension,
) -> None:
    template_extension_registry.register(
        extension
    )
