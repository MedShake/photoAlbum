from datetime import datetime
from pathlib import Path

from photoalbum.album import (
    AlbumBuilder,
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PhotoPageSettings,
    PlanItemKind,
    PrintConstraints,
    SpecialPage,
    TemplateDefinition,
    TemplateKind,
    TemplateRegistry,
)
from photoalbum.models import DateSource, Photo


def make_photo(
    filename: str,
    year: int,
    month: int,
    day: int,
) -> Photo:
    return Photo(
        path=Path("/photos") / filename,
        filename=filename,
        capture_datetime=datetime(
            year,
            month,
            day,
        ),
        date_source=DateSource.EXIF,
    )


def make_registry() -> TemplateRegistry:
    return TemplateRegistry(
        [
            TemplateDefinition(
                template_id="cover",
                name="Cover",
                allowed_kinds=frozenset({TemplateKind.COVER}),
            ),
            TemplateDefinition(
                template_id="month",
                name="Month divider",
                allowed_kinds=frozenset({TemplateKind.MONTH_DIVIDER}),
            ),
            TemplateDefinition(
                template_id="year",
                name="Year divider",
                allowed_kinds=frozenset({TemplateKind.YEAR_DIVIDER}),
            ),
            TemplateDefinition(
                template_id="photo-2",
                name="Two photos",
                allowed_kinds=frozenset({TemplateKind.PHOTO_PAGE}),
                photo_capacity=2,
            ),
            TemplateDefinition(
                template_id="index",
                name="Index",
                allowed_kinds=frozenset({TemplateKind.SPECIAL_PAGE}),
            ),
        ]
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
            placement=DividerPlacement.RIGHT_PAGE,
        ),
        year_dividers=DividerSettings(
            enabled=True,
            template_id="year",
            placement=DividerPlacement.RIGHT_PAGE,
        ),
        photo_pages=PhotoPageSettings(
            template_id="photo-2",
        ),
        front_matter=[
            SpecialPage(
                template_id="index",
            )
        ],
    )


def test_builder_creates_complete_album_result():
    photos = [
        make_photo(
            "march-1.jpg",
            2025,
            3,
            1,
        ),
        make_photo(
            "march-2.jpg",
            2025,
            3,
            2,
        ),
        make_photo(
            "march-3.jpg",
            2025,
            3,
            3,
        ),
        make_photo(
            "april.jpg",
            2025,
            4,
            1,
        ),
    ]

    result = AlbumBuilder(
        make_registry()
    ).build(
        photos,
        make_settings(),
    )

    assert result.plan.items
    assert result.pagination.pages


def test_builder_adds_year_divider_for_single_year():
    photos = [
        make_photo(
            "march.jpg",
            2025,
            3,
            1,
        ),
        make_photo(
            "april.jpg",
            2025,
            4,
            1,
        ),
    ]

    result = AlbumBuilder(
        make_registry()
    ).build(
        photos,
        make_settings(),
    )

    year_dividers = [
        item
        for item in result.plan.items
        if item.kind == PlanItemKind.YEAR_DIVIDER
    ]

    assert len(year_dividers) == 1
    assert year_dividers[0].year == 2025


def test_builder_uses_year_dividers_for_multiple_years():
    photos = [
        make_photo(
            "december.jpg",
            2025,
            12,
            1,
        ),
        make_photo(
            "january.jpg",
            2026,
            1,
            1,
        ),
    ]

    result = AlbumBuilder(
        make_registry()
    ).build(
        photos,
        make_settings(),
    )

    years = [
        item.year
        for item in result.plan.items
        if item.kind == PlanItemKind.YEAR_DIVIDER
    ]

    assert years == [2025, 2026]


def test_builder_preserves_front_matter():
    photos = [
        make_photo(
            "photo.jpg",
            2025,
            3,
            1,
        )
    ]

    result = AlbumBuilder(
        make_registry()
    ).build(
        photos,
        make_settings(),
    )

    assert result.plan.items[0].kind == (
        PlanItemKind.SPECIAL_PAGE
    )
    assert result.plan.items[0].template_id == "index"


def test_builder_reports_optional_print_constraint():
    photos = [
        make_photo(
            "photo.jpg",
            2025,
            3,
            1,
        )
    ]

    result = AlbumBuilder(
        make_registry()
    ).build(
        photos,
        make_settings(),
        print_constraints=PrintConstraints(
            page_multiple=4,
        ),
    )

    assert result.print_diagnostic.page_count == len(
        result.pagination.pages
    )


def test_print_constraint_does_not_change_album_pages():
    photos = [
        make_photo(
            "photo.jpg",
            2025,
            3,
            1,
        )
    ]

    builder = AlbumBuilder(
        make_registry()
    )

    unrestricted = builder.build(
        photos,
        make_settings(),
    )

    constrained = builder.build(
        photos,
        make_settings(),
        print_constraints=PrintConstraints(
            page_multiple=4,
        ),
    )

    assert (
        len(unrestricted.pagination.pages)
        == len(constrained.pagination.pages)
    )

