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


def __getattr__(name: str):
    if name == "CalendarIndexSettingsWidget":
        from .settings import (
            CalendarIndexSettingsWidget,
        )

        return CalendarIndexSettingsWidget

    if name == "compose_calendar_index":
        from .composition import (
            compose_calendar_index,
        )

        return compose_calendar_index

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "CalendarIndexSettingsWidget",
    "compose_calendar_index",
    "register",
]
