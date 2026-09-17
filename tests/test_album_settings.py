from photoalbum.album import (
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PhotoPageSettings,
    SpecialPage,
)


def create_settings(
    *,
    year_dividers_enabled: bool = True,
) -> AlbumStructureSettings:
    covers = {
        position: CoverSettings(
            position=position,
            template_id=f"{position.value}-template",
        )
        for position in CoverPosition
    }

    return AlbumStructureSettings(
        covers=covers,
        month_dividers=DividerSettings(
            enabled=True,
            template_id="month-divider",
        ),
        year_dividers=DividerSettings(
            enabled=year_dividers_enabled,
            template_id="year-divider",
        ),
        photo_pages=PhotoPageSettings(
            template_id="photo-page",
        ),
    )


def test_album_has_four_cover_settings():
    settings = create_settings()

    assert len(settings.covers) == 4

    assert set(settings.covers) == set(CoverPosition)


def test_month_divider_has_one_global_template():
    settings = create_settings()

    assert settings.month_dividers.enabled is True
    assert (
        settings.month_dividers.template_id
        == "month-divider"
    )


def test_year_dividers_available_for_single_year():
    settings = create_settings()

    assert (
        settings.year_dividers_available({2025})
        is True
    )


def test_year_dividers_available_for_multiple_years():
    settings = create_settings()

    assert (
        settings.year_dividers_available(
            {2025, 2026}
        )
        is True
    )


def test_enabled_year_dividers_are_used_for_single_year():
    settings = create_settings(
        year_dividers_enabled=True,
    )

    assert (
        settings.should_use_year_dividers({2025})
        is True
    )


def test_enabled_year_dividers_are_used_for_multiple_years():
    settings = create_settings(
        year_dividers_enabled=True,
    )

    assert (
        settings.should_use_year_dividers(
            {2025, 2026}
        )
        is True
    )


def test_disabled_year_dividers_remain_unused():
    settings = create_settings(
        year_dividers_enabled=False,
    )

    assert (
        settings.should_use_year_dividers(
            {2025, 2026}
        )
        is False
    )


def test_divider_can_follow_natural_flow():
    divider = DividerSettings(
        enabled=True,
        template_id="month-divider",
        placement=DividerPlacement.NATURAL,
    )

    assert (
        divider.placement
        == DividerPlacement.NATURAL
    )


def test_divider_can_require_right_page():
    divider = DividerSettings(
        enabled=True,
        template_id="month-divider",
        placement=DividerPlacement.RIGHT_PAGE,
    )

    assert (
        divider.placement
        == DividerPlacement.RIGHT_PAGE
    )


def test_divider_can_reserve_blank_facing_page():
    divider = DividerSettings(
        enabled=True,
        template_id="month-divider",
        placement=(
            DividerPlacement.RIGHT_PAGE_WITH_BLANK_FACING
        ),
    )

    assert (
        divider.placement
        == DividerPlacement.RIGHT_PAGE_WITH_BLANK_FACING
    )


def test_special_pages_are_optional():
    settings = create_settings()

    assert settings.front_matter == []
    assert settings.back_matter == []


def test_special_pages_preserve_user_order():
    settings = create_settings()

    settings.front_matter.extend(
        [
            SpecialPage(template_id="index"),
            SpecialPage(template_id="dedication"),
        ]
    )

    assert [
        page.template_id
        for page in settings.front_matter
    ] == [
        "index",
        "dedication",
    ]


def test_photo_pages_have_one_default_template():
    settings = create_settings()

    assert (
        settings.photo_pages.template_id
        == "photo-page"
    )

