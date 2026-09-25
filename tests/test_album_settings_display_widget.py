from photoalbum.templates.msb.photo_page.caption_style import caption_show_datetime, caption_show_location
from dataclasses import replace

from PySide6.QtWidgets import QApplication

from photoalbum.album import (
    PageNumberSettings,
)
from photoalbum.template_engine import create_template_registry

from photoalbum.gui.widgets import AlbumSettingsWidget
from photoalbum.i18n import Translator


def create_widget() -> AlbumSettingsWidget:
    application = QApplication.instance()

    if application is None:
        QApplication([])

    return AlbumSettingsWidget(
        create_template_registry(),
        translator=Translator("en"),
    )


def test_display_options_are_enabled_by_default():
    widget = create_widget()

    settings = widget.settings()

    assert caption_show_datetime(settings.photo_pages.page.settings)
    assert caption_show_location(settings.photo_pages.page.settings)
    assert settings.page_numbers.enabled


def test_display_options_can_be_restored():
    widget = create_widget()

    original = widget.settings()

    changed = replace(
        original,
        photo_pages=replace(
            original.photo_pages,
            page=original.photo_pages.page.with_settings({"photo_caption": {"show_datetime": False, "show_location": True}}),
        ),
        page_numbers=PageNumberSettings(
            enabled=False,
        ),
    )

    widget.set_settings(changed)

    assert widget.settings() == changed


def test_reset_restores_display_defaults():
    widget = create_widget()

    widget._page_numbers_checkbox.setChecked(False)

    widget.reset_to_defaults()

    settings = widget.settings()

    assert caption_show_datetime(settings.photo_pages.page.settings)
    assert caption_show_location(settings.photo_pages.page.settings)
    assert settings.page_numbers.enabled
