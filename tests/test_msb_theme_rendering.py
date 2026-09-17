from inspect import signature

from photoalbum.rendering.page_renderer import PageRenderer
from photoalbum.templates.msb.calendar_index.composition import (
    compose_calendar_index,
)
from photoalbum.templates.msb.calendar_index.widget_renderer import (
    CalendarIndexWidgetRenderer,
)
from photoalbum.templates.msb.geographic_word_cloud.widget_renderer import (
    GeographicWordCloudWidgetRenderer,
)
from photoalbum.templates.msb.month_divider_classic.widget_renderer import (
    MonthDividerClassicWidgetRenderer,
)
from photoalbum.templates.msb.theme import (
    DEFAULT_MONTH_COLORS,
    MsbTheme,
    msb_theme_from_pack_settings,
    pack_settings_with_msb_theme,
)


def test_custom_theme_round_trips_through_pack_settings():
    colors = dict(DEFAULT_MONTH_COLORS)
    colors[1] = (1, 2, 3)
    colors[12] = (250, 249, 248)

    theme = MsbTheme(
        month_colors=colors,
        default_font_family="DejaVu Serif",
    )

    stored = pack_settings_with_msb_theme(
        {"another_pack": {"keep": True}},
        theme,
    )

    restored = msb_theme_from_pack_settings(
        stored
    )

    assert restored.month_colors[1] == (1, 2, 3)
    assert restored.month_colors[12] == (250, 249, 248)
    assert restored.default_font_family == "DejaVu Serif"
    assert stored["another_pack"] == {"keep": True}


def test_calendar_accepts_project_theme_palette():
    colors = dict(DEFAULT_MONTH_COLORS)
    colors[1] = (1, 2, 3)
    colors[7] = (4, 5, 6)

    composition = compose_calendar_index(
        [],
        year=2025,
        month_colors=colors,
    )

    assert composition.months[0].color == (1, 2, 3)
    assert composition.months[6].color == (4, 5, 6)


def test_page_renderer_accepts_generic_pack_context():
    parameters = signature(
        PageRenderer.paint
    ).parameters

    assert "template_pack_settings" in parameters


def test_theme_dependent_msb_renderers_accept_pack_context():
    renderer_types = (
        CalendarIndexWidgetRenderer,
        MonthDividerClassicWidgetRenderer,
        GeographicWordCloudWidgetRenderer,
    )

    for renderer_type in renderer_types:
        parameters = signature(
            renderer_type.paint
        ).parameters

        assert "template_pack_settings" in parameters
