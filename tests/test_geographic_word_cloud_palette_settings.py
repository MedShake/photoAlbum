from pathlib import Path

from PySide6.QtWidgets import QApplication

from photoalbum.album import PageInstance
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.templates.msb.geographic_word_cloud.settings import (
    GeographicWordCloudSettingsWidget,
)
from photoalbum.templates.msb.theme import (
    MsbTheme,
    pack_settings_with_msb_theme,
)


def ensure_app():
    return QApplication.instance() or QApplication([])


def make_editor(
    *,
    instance=None,
    theme=None,
):
    ensure_app()

    if instance is None:
        instance = PageInstance(
            template_id="geographic-word-cloud"
        )

    if theme is None:
        theme = MsbTheme()

    pack_settings = pack_settings_with_msb_theme(
        {},
        theme,
    )

    return GeographicWordCloudSettingsWidget(
        instance,
        [
            Photo(
                path=Path("test.jpg"),
                filename="test.jpg",
            )
        ],
        translator=Translator("fr"),
        template_pack_settings=pack_settings,
    )


def test_word_cloud_initially_inherits_theme_palette():
    theme = MsbTheme()
    theme.month_colors[1] = (1, 2, 3)

    editor = make_editor(theme=theme)

    assert editor._has_local_palette is False
    assert editor._palette[1] == (1, 2, 3)

    settings = editor.instance().settings.get(
        "geographic_word_cloud",
        {},
    )

    assert "palette" not in settings

    editor.close()


def test_word_cloud_local_palette_is_preserved():
    theme = MsbTheme()
    theme.month_colors[1] = (1, 2, 3)

    instance = PageInstance(
        template_id="geographic-word-cloud",
        settings={
            "geographic_word_cloud": {
                "palette": [
                    [99, 98, 97],
                    *[
                        list(theme.month_colors[month])
                        for month in range(2, 13)
                    ],
                ]
            }
        },
    )

    editor = make_editor(
        instance=instance,
        theme=theme,
    )

    assert editor._has_local_palette is True
    assert editor._palette[1] == (99, 98, 97)

    editor.close()


def test_restore_theme_palette_removes_local_override():
    theme = MsbTheme()
    theme.month_colors[1] = (10, 20, 30)

    instance = PageInstance(
        template_id="geographic-word-cloud",
        settings={
            "geographic_word_cloud": {
                "palette": [
                    [99, 98, 97],
                    *[
                        list(theme.month_colors[month])
                        for month in range(2, 13)
                    ],
                ]
            }
        },
    )

    editor = make_editor(
        instance=instance,
        theme=theme,
    )

    assert editor._has_local_palette is True

    editor._restore_theme_palette()

    assert editor._has_local_palette is False
    assert editor._palette[1] == (10, 20, 30)

    settings = editor.instance().settings[
        "geographic_word_cloud"
    ]

    assert "palette" not in settings

    editor.close()


def test_restored_word_cloud_follows_later_theme_change():
    original_theme = MsbTheme()
    original_theme.month_colors[1] = (10, 20, 30)

    instance = PageInstance(
        template_id="geographic-word-cloud",
        settings={
            "geographic_word_cloud": {
                "palette": [
                    [99, 98, 97],
                    *[
                        list(
                            original_theme.month_colors[month]
                        )
                        for month in range(2, 13)
                    ],
                ]
            }
        },
    )

    editor = make_editor(
        instance=instance,
        theme=original_theme,
    )

    editor._restore_theme_palette()
    restored_instance = editor.instance()
    editor.close()

    later_theme = MsbTheme()
    later_theme.month_colors[1] = (200, 100, 50)

    reopened = make_editor(
        instance=restored_instance,
        theme=later_theme,
    )

    assert reopened._has_local_palette is False
    assert reopened._palette[1] == (200, 100, 50)

    reopened.close()
