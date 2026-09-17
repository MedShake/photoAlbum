from photoalbum.templates.msb.theme import (
    DEFAULT_MONTH_COLORS,
    MsbTheme,
    default_month_colors,
    msb_theme_from_pack_settings,
    pack_settings_with_msb_theme,
    palette_from_settings,
    palette_to_settings,
)


def test_msb_default_theme_materializes_all_month_colors():
    theme = MsbTheme()

    assert set(theme.month_colors) == set(range(1, 13))
    assert theme.month_colors == DEFAULT_MONTH_COLORS


def test_default_palette_is_not_shared_mutable_state():
    first = default_month_colors()
    second = default_month_colors()

    first[1] = (1, 2, 3)

    assert second[1] == DEFAULT_MONTH_COLORS[1]


def test_msb_theme_round_trip():
    colors = default_month_colors()
    colors[1] = (1, 2, 3)
    colors[12] = (250, 240, 230)

    theme = MsbTheme(
        month_colors=colors,
    )

    restored = MsbTheme.from_data(
        theme.to_data()
    )

    assert restored.month_colors == colors


def test_invalid_theme_colors_fall_back_individually():
    data = {
        "month_colors": {
            "1": [10, 20, 30],
            "2": [-1, 20, 30],
            "3": "invalid",
        }
    }

    theme = MsbTheme.from_data(data)

    assert theme.month_colors[1] == (10, 20, 30)
    assert theme.month_colors[2] == DEFAULT_MONTH_COLORS[2]
    assert theme.month_colors[3] == DEFAULT_MONTH_COLORS[3]


def test_pack_settings_preserve_other_packs_and_msb_values():
    initial = {
        "other-pack": {
            "something": 42,
        },
        "msb": {
            "future_setting": "preserve-me",
        },
    }

    colors = default_month_colors()
    colors[5] = (11, 22, 33)
    theme = MsbTheme(month_colors=colors)

    result = pack_settings_with_msb_theme(
        initial,
        theme,
    )

    assert result["other-pack"] == {
        "something": 42,
    }
    assert result["msb"]["future_setting"] == "preserve-me"

    restored = msb_theme_from_pack_settings(
        result
    )
    assert restored.month_colors[5] == (11, 22, 33)


def test_local_palette_round_trip():
    colors = default_month_colors()
    colors[7] = (7, 8, 9)

    encoded = palette_to_settings(colors)
    restored = palette_from_settings(encoded)

    assert restored == colors
