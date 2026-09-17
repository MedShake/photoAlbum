from __future__ import annotations


def register() -> None:
    from photoalbum.template_engine.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )
    from .settings import BlankSettingsWidget
    from .widget_renderer import BlankWidgetRenderer

    register_template_extension(
        PageTemplateExtension(
            template_id="blank",
            settings_editor_type=BlankSettingsWidget,
            widget_renderer=BlankWidgetRenderer(),
        )
    )


__all__ = [
    "register",
]
