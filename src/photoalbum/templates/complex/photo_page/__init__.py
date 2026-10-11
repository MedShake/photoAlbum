from __future__ import annotations

TEMPLATE_IDS = tuple(f"complex-photo-{n}" for n in range(1, 6))


def register() -> None:
    from photoalbum.template_engine.extensions import PageTemplateExtension, register_template_extension
    from .settings import ComplexPhotoPageSettingsWidget
    from .widget_renderer import PhotoPageWidgetRenderer
    renderer = PhotoPageWidgetRenderer()
    for template_id in TEMPLATE_IDS:
        register_template_extension(PageTemplateExtension(
            template_id=template_id,
            settings_editor_type=ComplexPhotoPageSettingsWidget,
            widget_renderer=renderer,
        ))


def register_layouts(registry) -> None:
    from .layout import register_layouts as register_photo_layouts
    register_photo_layouts(registry)
