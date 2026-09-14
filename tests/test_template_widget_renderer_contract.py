import inspect

from photoalbum.templates import (
    register_builtin_template_extensions,
    template_extension_registry,
)


EXPECTED_PARAMETERS = {
    "painter",
    "instance",
    "photos",
    "target_rect",
    "width",
    "height",
    "translator",
    "render_service",
    "set_waiting_key",
    "font_pixel_size",
    "page_width_mm",
    "page_height_mm",
    "album_pages",
    "composition",
    "thumbnail_cache",
    "pixel_rect",
}


def test_widget_renderers_follow_common_contract():
    register_builtin_template_extensions()

    for extension in (
        template_extension_registry
        ._extensions
        .values()
    ):
        renderer = extension.widget_renderer

        if renderer is None:
            continue

        parameters = set(
            inspect.signature(
                renderer.paint
            ).parameters
        )

        assert (
            EXPECTED_PARAMETERS
            <= parameters
        ), (
            f"{extension.template_id}: "
            f"missing "
            f"{EXPECTED_PARAMETERS - parameters}"
        )
