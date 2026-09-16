from __future__ import annotations


def register() -> None:
    from photoalbum.templates.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )
    from photoalbum.templates.renderers import (
        SimpleLabelWidgetRenderer,
    )

    register_template_extension(
        PageTemplateExtension(
            template_id="blank",
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
