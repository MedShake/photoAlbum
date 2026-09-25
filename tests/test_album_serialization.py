from photoalbum.album import (
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PhotoPageSettings,
    SpecialPage,
    album_settings_from_json,
    album_settings_to_json,
)


def test_custom_format_roundtrip_and_legacy_defaults():
    import json
    from dataclasses import replace
    from photoalbum.album import PageOrientation

    settings = replace(create_settings(), page_format="custom", custom_width_mm=321.5,
                       custom_height_mm=145.25, orientation=PageOrientation.LANDSCAPE)
    restored = album_settings_from_json(album_settings_to_json(settings))
    assert restored == settings
    page = restored.effective_page_format()
    assert (page.width_mm, page.height_mm) == (321.5, 145.25)
    data = json.loads(album_settings_to_json(create_settings()))
    data.pop("custom_width_mm")
    data.pop("custom_height_mm")
    legacy = album_settings_from_json(json.dumps(data))
    assert (legacy.custom_width_mm, legacy.custom_height_mm) == (210, 297)


def test_old_unversioned_album_settings_are_rejected():
    import json
    import pytest

    data = json.loads(album_settings_to_json(create_settings()))
    assert data['schema_version'] == 2
    assert set(data['photo_pages']) == {'page'}
    data.pop('schema_version')
    with pytest.raises(ValueError, match='Unsupported album settings schema'):
        album_settings_from_json(json.dumps(data))


def create_settings() -> AlbumStructureSettings:
    return AlbumStructureSettings(
        covers={
            position: CoverSettings(
                position=position,
                template_id=f"{position.value}-template",
            )
            for position in CoverPosition
        },
        month_dividers=DividerSettings(
            enabled=True,
            template_id="month-divider",
            placement=DividerPlacement.RIGHT_PAGE,
        ),
        year_dividers=DividerSettings(
            enabled=False,
            template_id="year-divider",
            placement=DividerPlacement.NATURAL,
        ),
        photo_pages=PhotoPageSettings(
            template_id="photo-page-4",
        ),
        front_matter=[
            SpecialPage(template_id="index"),
            SpecialPage(template_id="dedication"),
        ],
        back_matter=[
            SpecialPage(template_id="calendar-index"),
        ],
    )


def test_album_settings_round_trip():
    original = create_settings()

    encoded = album_settings_to_json(original)
    restored = album_settings_from_json(encoded)

    assert restored == original


def test_special_page_order_is_preserved():
    original = create_settings()

    restored = album_settings_from_json(
        album_settings_to_json(original)
    )

    assert [
        page.template_id
        for page in restored.front_matter
    ] == [
        "index",
        "dedication",
    ]


def test_divider_placement_is_preserved():
    original = create_settings()

    restored = album_settings_from_json(
        album_settings_to_json(original)
    )

    assert (
        restored.month_dividers.placement
        == DividerPlacement.RIGHT_PAGE
    )

    assert (
        restored.year_dividers.placement
        == DividerPlacement.NATURAL
    )
