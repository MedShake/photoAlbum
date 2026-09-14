from __future__ import annotations


def register() -> None:
    from photoalbum.templates.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )
    from photoalbum.templates.simple_label import (
        SimpleLabelWidgetRenderer,
    )

    register_template_extension(
        PageTemplateExtension(
            template_id="year-divider-classic",
            widget_renderer=(
                SimpleLabelWidgetRenderer(
                    "preview.year_divider"
                )
            ),
        )
    )


__all__ = [
    "register",
]
