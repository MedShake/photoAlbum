from __future__ import annotations


def register() -> None:
    from photoalbum.template_engine.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )
    from photoalbum.template_engine.renderers import (
        SimpleLabelWidgetRenderer,
    )
    from .settings import BlankSettingsWidget

    register_template_extension(
        PageTemplateExtension(
            template_id="blank",
            settings_editor_type=BlankSettingsWidget,
            widget_renderer=(
                SimpleLabelWidgetRenderer(
                    "preview.special_page"
                )
            ),
        )
    )


__all__ = [
    "register",
]
