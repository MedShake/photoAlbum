from __future__ import annotations

def register() -> None:
    from photoalbum.template_engine.extensions import PageTemplateExtension, register_template_extension
    from .settings import MonthDividerSimpleSettingsWidget
    from .widget_renderer import MonthDividerSimpleWidgetRenderer
    register_template_extension(PageTemplateExtension(template_id="month-divider-simple", settings_editor_type=MonthDividerSimpleSettingsWidget, widget_renderer=MonthDividerSimpleWidgetRenderer()))

__all__=["register"]
