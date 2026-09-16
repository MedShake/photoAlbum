from photoalbum.templates import (
    register_discovered_template_extensions,
    template_extension_registry,
)
from photoalbum.templates.msb.photo_page.widget_renderer import (
    PhotoPageWidgetRenderer,
)


def test_all_photo_page_templates_share_renderer():
    register_discovered_template_extensions()

    for template_id in (
        "photo-page-1",
        "photo-page-2",
        "photo-page-3",
        "photo-page-4",
    ):
        extension = (
            template_extension_registry.get(
                template_id
            )
        )

        assert extension is not None

        assert isinstance(
            extension.widget_renderer,
            PhotoPageWidgetRenderer,
        )
