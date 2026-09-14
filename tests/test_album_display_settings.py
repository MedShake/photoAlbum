import json

from photoalbum.album import (
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerSettings,
    PageNumberSettings,
    PhotoCaptionSettings,
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
        photo_pages=PhotoPageSettings(
            template_id="photo-page-2",
            caption=PhotoCaptionSettings(
                show_datetime=False,
                show_location=True,
            ),
        ),
        page_numbers=PageNumberSettings(
            enabled=False,
        ),
    )


def test_caption_settings_round_trip():
    original = make_settings()

    restored = album_settings_from_json(
        album_settings_to_json(original)
    )

    assert restored.photo_pages.caption == (
        PhotoCaptionSettings(
            show_datetime=False,
            show_location=True,
        )
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

    assert settings.caption.show_datetime
    assert settings.caption.show_location


def test_page_number_settings_default_enabled():
    settings = PageNumberSettings()

    assert settings.enabled
