from __future__ import annotations


def register() -> None:
    from photoalbum.templates.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )

    from .settings import (
        DedicationSettingsWidget,
    )
    from .widget_renderer import (
        DedicationWidgetRenderer,
    )

    register_template_extension(
        PageTemplateExtension(
            template_id="dedication",
            settings_editor_type=(
                DedicationSettingsWidget
            ),
            widget_renderer=(
                DedicationWidgetRenderer()
            ),
        )
    )


__all__ = [
    "register",
]
