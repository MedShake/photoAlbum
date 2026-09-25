from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Callable

from photoalbum.template_engine.preview_backend import (
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
    - shared preview/PDF renderer and photo scope
    - optional settings defaults and validation
    """

    template_id: str

    settings_editor_type: type | None = None
    preview_backend: TemplatePreviewBackend | None = None
    widget_renderer: object | None = None
    photo_scope: str = "page"
    settings_defaults: Callable[[], dict[str, object]] | None = None
    validate_settings: Callable[[dict[str, object]], None] | None = None

    def __post_init__(self) -> None:
        if self.photo_scope not in {"page", "album"}:
            raise ValueError("photo_scope must be 'page' or 'album'.")


class PageTemplateExtensionRegistry:
    def __init__(self) -> None:
        self._extensions: dict[
            str,
            PageTemplateExtension,
        ] = {}

    def replace(self, extensions: dict[str, PageTemplateExtension]) -> None:
        self._extensions = dict(extensions)

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


_registration_target: ContextVar[dict[str, PageTemplateExtension] | None] = (
    ContextVar("template_extension_registration_target", default=None)
)


@contextmanager
def collect_template_extensions():
    """Collect a registration pass without changing the active extensions."""
    extensions: dict[str, PageTemplateExtension] = {}
    token = _registration_target.set(extensions)
    try:
        yield extensions
    finally:
        _registration_target.reset(token)


def register_template_extension(
    extension: PageTemplateExtension,
) -> None:
    target = _registration_target.get()
    if target is not None:
        if extension.template_id in target:
            raise ValueError(f"Duplicate template extension ID: {extension.template_id}")
        target[extension.template_id] = extension
        return
    template_extension_registry.register(
        extension
    )
