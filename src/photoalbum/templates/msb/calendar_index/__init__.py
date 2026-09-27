from __future__ import annotations


def register() -> None:
    from photoalbum.template_engine.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )

    from .settings import (
        CalendarIndexSettingsWidget,
    )
    from .widget_renderer import (
        CalendarIndexWidgetRenderer,
    )

    register_template_extension(
        PageTemplateExtension(
            template_id="calendar-index",
            photo_scope="album",
            settings_editor_type=(
                CalendarIndexSettingsWidget
            ),
            widget_renderer=(
                CalendarIndexWidgetRenderer()
            ),
        )
    )


__all__ = ["register"]
