from datetime import datetime
from pathlib import Path

from photoalbum.album import (
    AlbumPlanner,
    AlbumStructureSettings,
    CoverPosition,
    CoverSettings,
    DividerSettings,
    PhotoPageSettings,
    PlanItemKind,
    SpecialPage,
)
from photoalbum.models import DateSource, Photo


def photo(
    filename: str,
    date: datetime | None,
) -> Photo:
    return Photo(
        path=Path("/photos") / filename,
        filename=filename,
        capture_datetime=date,
        date_source=(
            DateSource.EXIF
            if date is not None
            else DateSource.UNKNOWN
        ),
    )


def settings(
    *,
    months: bool = True,
    years: bool = True,
) -> AlbumStructureSettings:
    return AlbumStructureSettings(
        covers={
            position: CoverSettings(
                position=position,
                template_id="cover",
            )
            for position in CoverPosition
        },
        month_dividers=DividerSettings(
            enabled=months,
            template_id="month",
        ),
        year_dividers=DividerSettings(
            enabled=years,
            template_id="year",
        ),
        photo_pages=PhotoPageSettings(
            template_id="photo",
        ),
    )


def test_photos_are_grouped_by_month():
    planner = AlbumPlanner()

    plan = planner.plan(
        [
            photo("a.jpg", datetime(2025, 3, 1)),
            photo("b.jpg", datetime(2025, 3, 15)),
            photo("c.jpg", datetime(2025, 4, 2)),
        ],
        settings(),
    )

    groups = [
        item
        for item in plan.items
        if item.kind == PlanItemKind.PHOTO_GROUP
    ]

    assert len(groups) == 2

    assert [
        p.filename
        for p in groups[0].photos
    ] == [
        "a.jpg",
        "b.jpg",
    ]

    assert [
        p.filename
        for p in groups[1].photos
    ] == [
        "c.jpg",
    ]


def test_photos_are_sorted_chronologically():
    planner = AlbumPlanner()

    plan = planner.plan(
        [
            photo("c.jpg", datetime(2025, 3, 20)),
            photo("a.jpg", datetime(2025, 3, 1)),
            photo("b.jpg", datetime(2025, 3, 10)),
        ],
        settings(),
    )

    group = next(
        item
        for item in plan.items
        if item.kind == PlanItemKind.PHOTO_GROUP
    )

    assert [
        p.filename
        for p in group.photos
    ] == [
        "a.jpg",
        "b.jpg",
        "c.jpg",
    ]


def test_month_divider_precedes_photo_group():
    plan = AlbumPlanner().plan(
        [
            photo("a.jpg", datetime(2025, 3, 1)),
        ],
        settings(),
    )

    assert [
        item.kind
        for item in plan.items
    ] == [
        PlanItemKind.MONTH_DIVIDER,
        PlanItemKind.PHOTO_GROUP,
    ]


def test_month_dividers_can_be_disabled():
    plan = AlbumPlanner().plan(
        [
            photo("a.jpg", datetime(2025, 3, 1)),
            photo("b.jpg", datetime(2025, 4, 1)),
        ],
        settings(months=False),
    )

    assert all(
        item.kind != PlanItemKind.MONTH_DIVIDER
        for item in plan.items
    )


def test_single_year_has_no_year_divider():
    plan = AlbumPlanner().plan(
        [
            photo("a.jpg", datetime(2025, 3, 1)),
            photo("b.jpg", datetime(2025, 4, 1)),
        ],
        settings(years=True),
    )

    assert all(
        item.kind != PlanItemKind.YEAR_DIVIDER
        for item in plan.items
    )


def test_multiple_years_have_year_dividers():
    plan = AlbumPlanner().plan(
        [
            photo("a.jpg", datetime(2025, 12, 1)),
            photo("b.jpg", datetime(2026, 1, 1)),
        ],
        settings(years=True),
    )

    dividers = [
        item
        for item in plan.items
        if item.kind == PlanItemKind.YEAR_DIVIDER
    ]

    assert [
        item.year
        for item in dividers
    ] == [
        2025,
        2026,
    ]


def test_front_matter_precedes_album_body():
    album_settings = settings()

    album_settings.front_matter.extend(
        [
            SpecialPage(template_id="index"),
            SpecialPage(template_id="dedication"),
        ]
    )

    plan = AlbumPlanner().plan(
        [
            photo("a.jpg", datetime(2025, 3, 1)),
        ],
        album_settings,
    )

    assert [
        item.template_id
        for item in plan.items[:2]
    ] == [
        "index",
        "dedication",
    ]


def test_back_matter_follows_album_body():
    album_settings = settings()

    album_settings.back_matter.extend(
        [
            SpecialPage(template_id="calendar"),
            SpecialPage(template_id="credits"),
        ]
    )

    plan = AlbumPlanner().plan(
        [
            photo("a.jpg", datetime(2025, 3, 1)),
        ],
        album_settings,
    )

    assert [
        item.template_id
        for item in plan.items[-2:]
    ] == [
        "calendar",
        "credits",
    ]


def test_undated_photos_are_not_planned():
    plan = AlbumPlanner().plan(
        [
            photo("dated.jpg", datetime(2025, 3, 1)),
            photo("unknown.jpg", None),
        ],
        settings(),
    )

    planned_photos = [
        p
        for item in plan.items
        if item.kind == PlanItemKind.PHOTO_GROUP
        for p in item.photos
    ]

    assert [
        p.filename
        for p in planned_photos
    ] == [
        "dated.jpg",
    ]

