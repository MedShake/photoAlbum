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
            settings_editor_type=(
                GeographicWordCloudSettingsWidget
            ),
            widget_renderer=(
                GeographicWordCloudWidgetRenderer()
            ),
        )
    )


def __getattr__(name: str):
    if name == "GeographicWordCloudSettingsWidget":
        from .settings import (
            GeographicWordCloudSettingsWidget,
        )

        return GeographicWordCloudSettingsWidget

    if name == "compose_geographic_word_cloud":
        from .composition import (
            compose_geographic_word_cloud,
        )

        return compose_geographic_word_cloud

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "GeographicWordCloudSettingsWidget",
    "compose_geographic_word_cloud",
    "register",
]
