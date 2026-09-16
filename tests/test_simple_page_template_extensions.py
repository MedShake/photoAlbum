from photoalbum.template_engine import (
    register_discovered_template_extensions,
    template_extension_registry,
)
from photoalbum.template_engine.renderers import (
    SimpleLabelWidgetRenderer,
)
from photoalbum.templates.msb.year_divider_classic.widget_renderer import (
    YearDividerClassicWidgetRenderer,
)


def test_year_divider_owns_renderer():
    register_discovered_template_extensions()

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
    from photoalbum.templates.msb.dedication.settings import (
        DedicationSettingsWidget,
    )
    from photoalbum.templates.msb.dedication.widget_renderer import (
        DedicationWidgetRenderer,
    )

    register_discovered_template_extensions()

    extension = (
        template_extension_registry.get(
            "dedication"
        )
    )

    assert extension is not None

    assert (
        extension.settings_editor_type
        is DedicationSettingsWidget
    )

    assert isinstance(
        extension.widget_renderer,
        DedicationWidgetRenderer,
    )


def test_blank_template_owns_renderer():
    register_discovered_template_extensions()

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
