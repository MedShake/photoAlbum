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
    from photoalbum.templates.photo_page import (
        register as register_photo_pages,
    )
    from photoalbum.templates.month_divider_classic import (
        register as register_month_divider_classic,
    )
    from photoalbum.templates.year_divider_classic import (
        register as register_year_divider_classic,
    )
    from photoalbum.templates.dedication import (
        register as register_dedication,
    )
    from photoalbum.templates.blank import (
        register as register_blank,
    )

    register_year_photo_scatter()
    register_geographic_word_cloud()
    register_calendar_index()
    register_photo_pages()
    register_month_divider_classic()
    register_year_divider_classic()
    register_dedication()
    register_blank()


__all__ = [
    "PageTemplateExtension",
    "PageTemplateExtensionRegistry",
    "register_builtin_template_extensions",
    "register_template_extension",
    "template_extension_registry",
]
