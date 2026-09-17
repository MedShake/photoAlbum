from __future__ import annotations


def register() -> None:
    from photoalbum.template_engine.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )

    from .settings import (
        MonthDividerClassicSettingsWidget,
    )

    from .widget_renderer import (
        MonthDividerClassicWidgetRenderer,
    )

    register_template_extension(
        PageTemplateExtension(
            template_id="month-divider-classic",
            settings_editor_type=(
                MonthDividerClassicSettingsWidget
            ),
            widget_renderer=(
                MonthDividerClassicWidgetRenderer()
            ),
        )
    )


__all__ = [
    "register",
]
