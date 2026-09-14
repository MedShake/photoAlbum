import pytest

from photoalbum.album import (
    AlbumSettingsValidator,
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerSettings,
    PhotoPageSettings,
    SpecialPage,
    TemplateDefinition,
    TemplateKind,
    TemplateRegistry,
)


def create_registry() -> TemplateRegistry:
    return TemplateRegistry(
        [
            TemplateDefinition(
                template_id="cover",
                name="Cover",
                kind=TemplateKind.COVER,
            ),
            TemplateDefinition(
                template_id="month",
                name="Month divider",
                kind=TemplateKind.MONTH_DIVIDER,
            ),
            TemplateDefinition(
                template_id="year",
                name="Year divider",
                kind=TemplateKind.YEAR_DIVIDER,
            ),
            TemplateDefinition(
                template_id="photo",
                name="Photo page",
                kind=TemplateKind.PHOTO_PAGE,
                photo_capacity=2,
            ),
            TemplateDefinition(
                template_id="index",
                name="Index",
                kind=TemplateKind.SPECIAL_PAGE,
            ),
            TemplateDefinition(
                template_id="dedication",
                name="Dedication",
                kind=TemplateKind.SPECIAL_PAGE,
            ),
        ]
    )


def create_settings() -> AlbumStructureSettings:
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
            template_id="photo",
        ),
        front_matter=[
            SpecialPage(template_id="index"),
        ],
        back_matter=[
            SpecialPage(template_id="dedication"),
        ],
    )


def test_valid_album_settings_are_accepted():
    validator = AlbumSettingsValidator(
        create_registry()
    )

    validator.validate(create_settings())


def test_unknown_template_is_rejected():
    settings = create_settings()
    settings.photo_pages = PhotoPageSettings(
        template_id="unknown"
    )

    validator = AlbumSettingsValidator(
        create_registry()
    )

    with pytest.raises(KeyError):
        validator.validate(settings)


def test_photo_pages_require_photo_page_template():
    settings = create_settings()
    settings.photo_pages = PhotoPageSettings(
        template_id="cover"
    )

    validator = AlbumSettingsValidator(
        create_registry()
    )

    with pytest.raises(ValueError):
        validator.validate(settings)


def test_cover_requires_cover_template():
    settings = create_settings()

    settings.covers[CoverPosition.FRONT] = (
        CoverSettings(
            position=CoverPosition.FRONT,
            template_id="photo",
        )
    )

    validator = AlbumSettingsValidator(
        create_registry()
    )

    with pytest.raises(ValueError):
        validator.validate(settings)


def test_month_divider_requires_month_template():
    settings = create_settings()

    settings.month_dividers = DividerSettings(
        enabled=True,
        template_id="year",
    )

    validator = AlbumSettingsValidator(
        create_registry()
    )

    with pytest.raises(ValueError):
        validator.validate(settings)


def test_year_divider_requires_year_template():
    settings = create_settings()

    settings.year_dividers = DividerSettings(
        enabled=True,
        template_id="month",
    )

    validator = AlbumSettingsValidator(
        create_registry()
    )

    with pytest.raises(ValueError):
        validator.validate(settings)


def test_front_matter_requires_special_page_template():
    settings = create_settings()

    settings.front_matter = [
        SpecialPage(template_id="photo")
    ]

    validator = AlbumSettingsValidator(
        create_registry()
    )

    with pytest.raises(ValueError):
        validator.validate(settings)


def test_back_matter_requires_special_page_template():
    settings = create_settings()

    settings.back_matter = [
        SpecialPage(template_id="cover")
    ]

    validator = AlbumSettingsValidator(
        create_registry()
    )

    with pytest.raises(ValueError):
        validator.validate(settings)

