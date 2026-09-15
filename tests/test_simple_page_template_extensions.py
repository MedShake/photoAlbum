from photoalbum.templates import (
    register_builtin_template_extensions,
    template_extension_registry,
)
from photoalbum.templates.simple_label import (
    SimpleLabelWidgetRenderer,
)
from photoalbum.templates.year_divider_classic.widget_renderer import (
    YearDividerClassicWidgetRenderer,
)


def test_year_divider_owns_renderer():
    register_builtin_template_extensions()

    extension = (
        template_extension_registry.get(
            "year-divider-classic"
        )
    )

    assert extension is not None

    assert isinstance(
        extension.widget_renderer,
        YearDividerClassicWidgetRenderer,
    )

    assert (
        extension.settings_editor_type
        is not None
    )


def test_dedication_owns_renderer():
    register_builtin_template_extensions()

    extension = (
        template_extension_registry.get(
            "dedication"
        )
    )

    assert extension is not None

    assert isinstance(
        extension.widget_renderer,
        SimpleLabelWidgetRenderer,
    )


def test_blank_template_owns_renderer():
    register_builtin_template_extensions()

    extension = (
        template_extension_registry.get(
            "blank"
        )
    )

    assert extension is not None

    assert isinstance(
        extension.widget_renderer,
        SimpleLabelWidgetRenderer,
    )
