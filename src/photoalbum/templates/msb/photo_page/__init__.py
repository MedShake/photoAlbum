from __future__ import annotations


PHOTO_PAGE_TEMPLATE_IDS = (
    "photo-page-1",
    "photo-page-2",
    "photo-page-3",
    "photo-page-4",
)


def register() -> None:
    from photoalbum.template_engine.extensions import (
        PageTemplateExtension,
        register_template_extension,
    )

    from .widget_renderer import (
        PhotoPageWidgetRenderer,
    )

    renderer = (
        PhotoPageWidgetRenderer()
    )

    for template_id in PHOTO_PAGE_TEMPLATE_IDS:
        register_template_extension(
            PageTemplateExtension(
                template_id=template_id,
                widget_renderer=renderer,
            )
        )


__all__ = [
    "PHOTO_PAGE_TEMPLATE_IDS",
    "register",
]
