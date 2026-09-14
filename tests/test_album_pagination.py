from datetime import datetime
from pathlib import Path

from photoalbum.album import (
    AlbumPlan,
    PageSide,
    PaginationEngine,
    PlanItem,
    PlanItemKind,
    TemplateDefinition,
    TemplateKind,
    TemplateRegistry,
    AlbumStructureSettings,
    BlankPageReason,
    CoverPosition,
    CoverSettings,
    DividerPlacement,
    DividerSettings,
    PhotoPageSettings,
)
from photoalbum.models import DateSource, Photo

def photo(
    filename: str,
    day: int,
) -> Photo:
    return Photo(
        path=Path("/photos") / filename,
        filename=filename,
        capture_datetime=datetime(
            2025,
            3,
            day,
        ),
        date_source=DateSource.EXIF,
    )


def registry(
    capacity: int = 2,
) -> TemplateRegistry:
    return TemplateRegistry(
        [
            TemplateDefinition(
                template_id="photo",
                name="Photo page",
                kind=TemplateKind.PHOTO_PAGE,
                photo_capacity=capacity,
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
                template_id="index",
                name="Index",
                kind=TemplateKind.SPECIAL_PAGE,
            ),
        ]
    )


def photo_group(
    photos: list[Photo],
) -> PlanItem:
    return PlanItem(
        kind=PlanItemKind.PHOTO_GROUP,
        template_id="photo",
        year=2025,
        month=3,
        photos=tuple(photos),
    )


def test_first_page_is_right():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.SPECIAL_PAGE,
                template_id="index",
            )
        ]
    )

    result = PaginationEngine(
        registry()
    ).paginate(plan)

    assert result.pages[0].number == 1
    assert result.pages[0].side == PageSide.RIGHT


def test_pages_alternate_right_and_left():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.SPECIAL_PAGE,
                template_id="index",
            ),
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=3,
            ),
            photo_group(
                [photo("a.jpg", 1)]
            ),
        ]
    )

    result = PaginationEngine(
        registry()
    ).paginate(plan)

    assert [
        page.side
        for page in result.pages
    ] == [
        PageSide.RIGHT,
        PageSide.LEFT,
        PageSide.RIGHT,
    ]


def test_two_photo_template_splits_photos():
    plan = AlbumPlan(
        items=[
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                    photo("c.jpg", 3),
                    photo("d.jpg", 4),
                    photo("e.jpg", 5),
                ]
            )
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(plan)

    assert len(result.pages) == 3

    assert [
        len(page.photos)
        for page in result.pages
    ] == [
        2,
        2,
        1,
    ]


def test_three_photo_template_splits_photos():
    plan = AlbumPlan(
        items=[
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                    photo("c.jpg", 3),
                    photo("d.jpg", 4),
                    photo("e.jpg", 5),
                    photo("f.jpg", 6),
                    photo("g.jpg", 7),
                ]
            )
        ]
    )

    result = PaginationEngine(
        registry(capacity=3)
    ).paginate(plan)

    assert [
        len(page.photos)
        for page in result.pages
    ] == [
        3,
        3,
        1,
    ]


def test_photo_order_is_preserved():
    photos = [
        photo("a.jpg", 1),
        photo("b.jpg", 2),
        photo("c.jpg", 3),
        photo("d.jpg", 4),
        photo("e.jpg", 5),
    ]

    plan = AlbumPlan(
        items=[
            photo_group(photos)
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(plan)

    paginated = [
        item
        for page in result.pages
        for item in page.photos
    ]

    assert [
        item.filename
        for item in paginated
    ] == [
        "a.jpg",
        "b.jpg",
        "c.jpg",
        "d.jpg",
        "e.jpg",
    ]


def test_last_photo_page_reports_unused_slots():
    plan = AlbumPlan(
        items=[
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                    photo("c.jpg", 3),
                ]
            )
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(plan)

    assert (
        result.pages[-1].unused_photo_slots
        == 1
    )


def test_full_photo_page_has_no_unused_slots():
    plan = AlbumPlan(
        items=[
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                ]
            )
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(plan)

    assert (
        result.pages[0].unused_photo_slots
        == 0
    )


def test_special_page_occupies_one_page():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.SPECIAL_PAGE,
                template_id="index",
            )
        ]
    )

    result = PaginationEngine(
        registry()
    ).paginate(plan)

    assert len(result.pages) == 1

    page = result.pages[0]

    assert page.kind == PlanItemKind.SPECIAL_PAGE
    assert page.template_id == "index"
    assert page.photo_capacity == 0


def test_month_divider_occupies_one_page():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=3,
            )
        ]
    )

    result = PaginationEngine(
        registry()
    ).paginate(plan)

    assert len(result.pages) == 1

    page = result.pages[0]

    assert page.year == 2025
    assert page.month == 3

def album_settings(
    *,
    month_placement: DividerPlacement,
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
            enabled=True,
            template_id="month",
            placement=month_placement,
        ),
        year_dividers=DividerSettings(
            enabled=False,
            template_id="year",
        ),
        photo_pages=PhotoPageSettings(
            template_id="photo",
        ),
    )


def test_right_page_month_divider_is_placed_on_right():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=3,
            ),
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                    photo("c.jpg", 3),
                ]
            ),
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=4,
            ),
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(
        plan,
        album_settings(
            month_placement=DividerPlacement.RIGHT_PAGE
        ),
    )

    april = result.pages[-1]

    assert april.kind == PlanItemKind.MONTH_DIVIDER
    assert april.month == 4
    assert april.side == PageSide.RIGHT


def test_right_page_policy_inserts_technical_blank():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=3,
            ),
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                    photo("c.jpg", 3),
                ]
            ),
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=4,
            ),
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(
        plan,
        album_settings(
            month_placement=DividerPlacement.RIGHT_PAGE
        ),
    )

    technical_blanks = [
        page
        for page in result.pages
        if (
            page.blank_reason
            == BlankPageReason.TECHNICAL
        )
    ]

    assert len(technical_blanks) == 1
    assert technical_blanks[0].side == PageSide.LEFT


def test_three_march_photos_leave_three_usable_slots_before_april():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=3,
            ),
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                    photo("c.jpg", 3),
                ]
            ),
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=4,
            ),
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(
        plan,
        album_settings(
            month_placement=DividerPlacement.RIGHT_PAGE
        ),
    )

    march = next(
        period
        for period in result.period_end_capacities
        if (
            period.year == 2025
            and period.month == 3
        )
    )

    assert march.unused_photo_slots == 3

def test_blank_facing_policy_keeps_left_page_empty():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=3,
            ),
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                    photo("c.jpg", 3),
                ]
            ),
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=4,
            ),
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(
        plan,
        album_settings(
            month_placement=(
                DividerPlacement.RIGHT_PAGE_WITH_BLANK_FACING
            )
        ),
    )

    april = result.pages[-1]
    facing = result.pages[-2]

    assert april.kind == PlanItemKind.MONTH_DIVIDER
    assert april.month == 4
    assert april.side == PageSide.RIGHT

    assert facing.side == PageSide.LEFT
    assert (
        facing.blank_reason
        == BlankPageReason.EDITORIAL
    )


def test_editorial_blank_does_not_count_as_usable_capacity():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=3,
            ),
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                    photo("c.jpg", 3),
                ]
            ),
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=4,
            ),
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(
        plan,
        album_settings(
            month_placement=(
                DividerPlacement.RIGHT_PAGE_WITH_BLANK_FACING
            )
        ),
    )

    march = next(
        period
        for period in result.period_end_capacities
        if (
            period.year == 2025
            and period.month == 3
        )
    )

    assert march.unused_photo_slots == 1

def test_blank_facing_may_require_technical_and_editorial_blank():
    plan = AlbumPlan(
        items=[
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=3,
            ),
            photo_group(
                [
                    photo("a.jpg", 1),
                    photo("b.jpg", 2),
                ]
            ),
            PlanItem(
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month",
                year=2025,
                month=4,
            ),
        ]
    )

    result = PaginationEngine(
        registry(capacity=2)
    ).paginate(
        plan,
        album_settings(
            month_placement=(
                DividerPlacement.RIGHT_PAGE_WITH_BLANK_FACING
            )
        ),
    )

    april = result.pages[-1]

    assert april.side == PageSide.RIGHT

    assert (
        result.pages[-2].blank_reason
        == BlankPageReason.EDITORIAL
    )

    assert (
        result.pages[-3].blank_reason
        == BlankPageReason.TECHNICAL
    )

    march = next(
        period
        for period in result.period_end_capacities
        if (
            period.year == 2025
            and period.month == 3
        )
    )

    assert march.unused_photo_slots == 2