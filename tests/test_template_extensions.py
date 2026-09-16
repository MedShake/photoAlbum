from photoalbum.template_engine import (
    register_discovered_template_extensions,
    template_extension_registry,
)
from photoalbum.templates.msb.year_photo_scatter import (
    YearPhotoScatterPreviewBackend,
    YearPhotoScatterSettingsWidget,
)


def test_scatter_owns_its_extension():
    register_discovered_template_extensions()

    extension = template_extension_registry.get(
        "year-photo-scatter"
    )

    assert extension is not None

    assert (
        extension.settings_editor_type
        is YearPhotoScatterSettingsWidget
    )

    assert isinstance(
        extension.preview_backend,
        YearPhotoScatterPreviewBackend,
    )


def test_unknown_template_has_no_extension():
    assert (
        template_extension_registry.get(
            "does-not-exist"
        )
        is None
    )
