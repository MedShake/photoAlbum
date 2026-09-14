from photoalbum.templates.extensions import (
    PageTemplateExtension,
    PageTemplateExtensionRegistry,
    register_template_extension,
    template_extension_registry,
)


def register_builtin_template_extensions() -> None:
    """
    Register executable behaviour owned by built-in templates.

    Adding another built-in template should only require
    adding its register() call here until automatic discovery
    is introduced.
    """

    from photoalbum.templates.year_photo_scatter import (
        register as register_year_photo_scatter,
    )
    from photoalbum.templates.geographic_word_cloud import (
        register as register_geographic_word_cloud,
    )
    from photoalbum.templates.calendar_index import (
        register as register_calendar_index,
    )

    register_year_photo_scatter()
    register_geographic_word_cloud()
    register_calendar_index()


__all__ = [
    "PageTemplateExtension",
    "PageTemplateExtensionRegistry",
    "register_builtin_template_extensions",
    "register_template_extension",
    "template_extension_registry",
]
