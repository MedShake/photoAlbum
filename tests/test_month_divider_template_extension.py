from photoalbum.templates import (
    register_discovered_template_extensions,
    template_extension_registry,
)
from photoalbum.templates.msb.month_divider_classic.widget_renderer import (
    MonthDividerClassicWidgetRenderer,
)


def test_classic_month_divider_owns_renderer():
    register_discovered_template_extensions()

    extension = (
        template_extension_registry.get(
            "month-divider-classic"
        )
    )

    assert extension is not None

    assert isinstance(
        extension.widget_renderer,
        MonthDividerClassicWidgetRenderer,
    )
