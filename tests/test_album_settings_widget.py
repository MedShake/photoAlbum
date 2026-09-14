from PySide6.QtWidgets import QApplication

from photoalbum.album import (
    DividerPlacement,
    create_builtin_template_registry,
)
from photoalbum.gui.widgets import AlbumSettingsWidget


def create_widget() -> AlbumSettingsWidget:
    application = QApplication.instance()

    if application is None:
        QApplication([])

    return AlbumSettingsWidget(
        create_builtin_template_registry()
    )


def test_default_photo_template_is_two_photos():
    widget = create_widget()

    settings = widget.settings()

    assert (
        settings.photo_pages.template_id
        == "photo-page-2"
    )


def test_default_month_dividers_are_enabled():
    widget = create_widget()

    settings = widget.settings()

    assert settings.month_dividers.enabled
    assert (
        settings.month_dividers.placement
        == DividerPlacement.RIGHT_PAGE
    )


def test_year_dividers_are_disabled_for_one_year():
    widget = create_widget()

    widget.set_available_years({2025})

    settings = widget.settings()

    assert not settings.year_dividers.enabled


def test_year_dividers_are_available_for_multiple_years():
    widget = create_widget()

    widget.set_available_years(
        {2025, 2026}
    )

    settings = widget.settings()

    assert settings.year_dividers.enabled

