from .base import PageTemplateSettingsWidget
from .registry import (
    TemplateSettingsEditorRegistry,
    create_template_settings_editor,
    register_template_settings_editor,
)

__all__ = [
    "PageTemplateSettingsWidget",
    "TemplateSettingsEditorRegistry",
    "create_template_settings_editor",
    "register_template_settings_editor",
]
