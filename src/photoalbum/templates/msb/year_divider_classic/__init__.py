from __future__ import annotations


def register() -> None:
    from photoalbum.templates.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )

    from .settings import (
        YearDividerClassicSettingsWidget,
    )
    from .widget_renderer import (
        YearDividerClassicWidgetRenderer,
    )

    register_template_extension(
        PageTemplateExtension(
            template_id="year-divider-classic",
            settings_editor_type=(
                YearDividerClassicSettingsWidget
            ),
            widget_renderer=(
                YearDividerClassicWidgetRenderer()
            ),
        )
    )


__all__ = [
    "register",
]
