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

