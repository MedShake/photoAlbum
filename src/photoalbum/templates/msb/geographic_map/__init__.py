from __future__ import annotations


def register() -> None:
    from photoalbum.template_engine.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )

    from .preview import (
        GeographicMapPreviewBackend,
    )
    from .settings import (
        GeographicMapSettingsWidget,
    )
    from .widget_renderer import (
        GeographicMapWidgetRenderer,
    )

    register_template_extension(
        PageTemplateExtension(
            template_id="geographic-map",
            photo_scope="album",
            settings_editor_type=(
                GeographicMapSettingsWidget
            ),
            preview_backend=(
                GeographicMapPreviewBackend()
            ),
            widget_renderer=(
                GeographicMapWidgetRenderer()
            ),
        )
    )


__all__ = ["register"]
