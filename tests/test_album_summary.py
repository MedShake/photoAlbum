from photoalbum.album import (
    AlbumBuildResult,
    AlbumPlan,
    AlbumSummaryBuilder,
    BlankPageReason,
    PageSide,
    PaginationResult,
    PeriodEndCapacity,
    PlanItemKind,
    PlannedPage,
    PrintDiagnostic,
)


def test_summary_counts_pages():
    result = AlbumBuildResult(
        plan=AlbumPlan(),
        pagination=PaginationResult(
            pages=[
                PlannedPage(
                    number=1,
                    side=PageSide.RIGHT,
                    kind=PlanItemKind.SPECIAL_PAGE,
                    template_id="index",
                ),
                PlannedPage(
                    number=2,
                    side=PageSide.LEFT,
                    kind=PlanItemKind.MONTH_DIVIDER,
                    template_id="month",
                    year=2025,
                    month=3,
                ),
                PlannedPage(
                    number=3,
                    side=PageSide.RIGHT,
                    kind=PlanItemKind.PHOTO_GROUP,
                    template_id="photo",
                    year=2025,
                    month=3,
                    photo_capacity=2,
                ),
                PlannedPage(
                    number=4,
                    side=PageSide.LEFT,
                    kind=None,
                    template_id="photo",
                    year=2025,
                    month=3,
                    photo_capacity=2,
                    blank_reason=BlankPageReason.TECHNICAL,
                ),
            ]
        ),
        print_diagnostic=PrintDiagnostic(
            page_count=4,
            compatible=True,
            pages_to_add=0,
        ),
    )

    summary = AlbumSummaryBuilder().build(result)

    assert summary.total_pages == 4
    assert summary.photo_pages == 1
    assert summary.divider_pages == 1
    assert summary.special_pages == 1
    assert summary.technical_blank_pages == 1
    assert summary.editorial_blank_pages == 0


def test_summary_exposes_print_warning():
    result = AlbumBuildResult(
        plan=AlbumPlan(),
        pagination=PaginationResult(),
        print_diagnostic=PrintDiagnostic(
            page_count=42,
            compatible=False,
            pages_to_add=2,
        ),
    )

    summary = AlbumSummaryBuilder().build(result)

    assert not summary.print_compatible
    assert summary.print_pages_to_add == 2


def test_summary_contains_period_fill_suggestions():
    result = AlbumBuildResult(
        plan=AlbumPlan(),
        pagination=PaginationResult(
            period_end_capacities=[
                PeriodEndCapacity(
                    year=2025,
                    month=3,
                    unused_photo_slots=3,
                ),
                PeriodEndCapacity(
                    year=2025,
                    month=4,
                    unused_photo_slots=0,
                ),
                PeriodEndCapacity(
                    year=2025,
                    month=5,
                    unused_photo_slots=1,
                ),
            ]
        ),
        print_diagnostic=PrintDiagnostic(
            page_count=0,
            compatible=True,
            pages_to_add=0,
        ),
    )

    summary = AlbumSummaryBuilder().build(result)

    assert [
        (
            item.year,
            item.month,
            item.available_photo_slots,
        )
        for item in summary.period_fill_suggestions
    ] == [
        (2025, 3, 3),
        (2025, 5, 1),
    ]


def test_summary_ignores_periods_without_free_slots():
    result = AlbumBuildResult(
        plan=AlbumPlan(),
        pagination=PaginationResult(
            period_end_capacities=[
                PeriodEndCapacity(
                    year=2025,
                    month=6,
                    unused_photo_slots=0,
                ),
            ]
        ),
        print_diagnostic=PrintDiagnostic(
            page_count=0,
            compatible=True,
            pages_to_add=0,
        ),
    )

    summary = AlbumSummaryBuilder().build(result)

    assert summary.period_fill_suggestions == ()

