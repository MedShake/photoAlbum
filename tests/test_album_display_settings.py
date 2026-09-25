from photoalbum.templates.msb.photo_page.caption_style import caption_show_datetime, caption_show_location
from photoalbum.album import PageInstance
import json

from photoalbum.album import (
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerSettings,
    PageNumberSettings,
    PhotoPageSettings,
    album_settings_from_json,
    album_settings_to_json,
)


def make_settings() -> AlbumStructureSettings:
    return AlbumStructureSettings(
        covers={
            position: CoverSettings(
                position=position,
                template_id="cover",
            )
            for position in CoverPosition
        },
        month_dividers=DividerSettings(
            enabled=True,
            template_id="month",
        ),
        year_dividers=DividerSettings(
            enabled=True,
            template_id="year",
        ),
        photo_pages=PhotoPageSettings(page=PageInstance(template_id='photo-page-2', settings={'photo_caption': {'show_datetime': False, 'show_location': True}})),
        page_numbers=PageNumberSettings(
            enabled=False,
        ),
    )


def test_caption_settings_round_trip():
    original = make_settings()

    restored = album_settings_from_json(
        album_settings_to_json(original)
    )

    assert restored.photo_pages.page.settings["photo_caption"] == (
        {"show_datetime": False, "show_location": True}
    )


def test_page_number_settings_round_trip():
    original = make_settings()

    restored = album_settings_from_json(
        album_settings_to_json(original)
    )

    assert not restored.page_numbers.enabled


def test_photo_page_settings_default_caption():
    settings = PhotoPageSettings(
        template_id="photo-page-2"
    )

    assert caption_show_datetime(settings.page.settings)
    assert caption_show_location(settings.page.settings)


def test_page_number_settings_default_enabled():
    settings = PageNumberSettings()

    assert settings.enabled
