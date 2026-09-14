from __future__ import annotations


def register() -> None:
    """
    Register the executable extension of the built-in
    year-photo-scatter template.

    Imports deliberately stay local so importing only the
    composition module does not pull GUI/settings/rendering
    dependencies into album core.
    """

    from photoalbum.templates.extensions import (
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


def __getattr__(
    name: str,
):
    """
    Lazy public exports.

    This preserves convenient imports such as:

        from photoalbum.templates.year_photo_scatter import (
            YearPhotoScatterPreviewBackend,
        )

    without eagerly importing GUI/rendering modules whenever
    composition.py alone is requested.
    """

    if name == "YearPhotoScatterPreviewBackend":
        from .preview import (
            YearPhotoScatterPreviewBackend,
        )

        return YearPhotoScatterPreviewBackend

    if name == "YearPhotoScatterSettingsWidget":
        from .settings import (
            YearPhotoScatterSettingsWidget,
        )

        return YearPhotoScatterSettingsWidget

    if name == "compose_cover_scatter":
        from .composition import (
            compose_cover_scatter,
        )

        return compose_cover_scatter

    if name == "visible_cover_scatter_items":
        from .composition import (
            visible_cover_scatter_items,
        )

        return visible_cover_scatter_items

    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "YearPhotoScatterPreviewBackend",
    "YearPhotoScatterSettingsWidget",
    "compose_cover_scatter",
    "register",
    "visible_cover_scatter_items",
]
