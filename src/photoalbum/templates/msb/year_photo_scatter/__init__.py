from __future__ import annotations


def register() -> None:
    """
    Register the executable extension of the built-in
    year-photo-scatter template.

    Imports deliberately stay local so importing only the
    composition module does not pull GUI/settings/rendering
    dependencies into album core.
    """

    from photoalbum.template_engine.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )

    from .preview import (
        YearPhotoScatterPreviewBackend,
    )
    from .settings import (
        YearPhotoScatterSettingsWidget,
    )
    from .widget_renderer import (
        YearPhotoScatterWidgetRenderer,
    )

    register_template_extension(
        PageTemplateExtension(
            template_id="year-photo-scatter",
            photo_scope="album",
            settings_editor_type=(
                YearPhotoScatterSettingsWidget
            ),
            preview_backend=(
                YearPhotoScatterPreviewBackend()
            ),
            widget_renderer=(
                YearPhotoScatterWidgetRenderer()
            ),
        )
    )


__all__ = ["register"]
