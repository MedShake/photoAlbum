from __future__ import annotations


def register() -> None:
    from photoalbum.template_engine.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )

    from .settings import (
        GeographicWordCloudSettingsWidget,
    )
    from .widget_renderer import (
        GeographicWordCloudWidgetRenderer,
    )

    register_template_extension(
        PageTemplateExtension(
            template_id="geographic-word-cloud",
            photo_scope="album",
            settings_editor_type=(
                GeographicWordCloudSettingsWidget
            ),
            widget_renderer=(
                GeographicWordCloudWidgetRenderer()
            ),
        )
    )


__all__ = ["register"]
