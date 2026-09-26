"""MSB's simple daily date separator."""


def register() -> None:
    from photoalbum.template_engine.api import PageTemplateExtension, register_template_extension
    from .settings import DayDividerSimpleSettingsWidget
    from .widget_renderer import DayDividerSimpleWidgetRenderer

    register_template_extension(PageTemplateExtension(
        template_id="day-divider-simple",
        settings_editor_type=DayDividerSimpleSettingsWidget,
        widget_renderer=DayDividerSimpleWidgetRenderer(),
    ))
