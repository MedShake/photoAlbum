from photoalbum.album import (
    PrintSettings,
)


def test_print_settings_default_has_no_page_multiple():
    settings = PrintSettings()

    assert settings.page_multiple is None


def test_print_settings_can_require_multiple_of_four():
    settings = PrintSettings(
        page_multiple=4,
    )

    assert settings.page_multiple == 4
