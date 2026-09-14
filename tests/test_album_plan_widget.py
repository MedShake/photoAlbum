import calendar

from PySide6.QtWidgets import QApplication

from photoalbum.album import (
    AlbumBuildResult,
    AlbumPlan,
    BlankPageReason,
    PageSide,
    PaginationResult,
    PeriodEndCapacity,
    PlanItemKind,
    PlannedPage,
    PrintDiagnostic,
)
from photoalbum.gui.widgets import AlbumPlanWidget


def create_widget() -> AlbumPlanWidget:
    application = QApplication.instance()

    if application is None:
        QApplication([])

    return AlbumPlanWidget()


def create_result() -> AlbumBuildResult:
    return AlbumBuildResult(
        plan=AlbumPlan(),
        pagination=PaginationResult(
            pages=[
                PlannedPage(
                    number=1,
                    side=PageSide.RIGHT,
                    kind=PlanItemKind.SPECIAL_PAGE,
                    template_id="calendar-index",
                ),
                PlannedPage(
                    number=2,
                    side=PageSide.LEFT,
                    kind=PlanItemKind.MONTH_DIVIDER,
                    template_id="month-divider-classic",
                    year=2025,
                    month=3,
                ),
                PlannedPage(
                    number=3,
                    side=PageSide.RIGHT,
                    kind=PlanItemKind.PHOTO_GROUP,
                    template_id="photo-page-2",
                    year=2025,
                    month=3,
                    photo_capacity=2,
                ),
                PlannedPage(
                    number=4,
                    side=PageSide.LEFT,
                    kind=None,
                    template_id="photo-page-2",
                    year=2025,
                    month=3,
                    photo_capacity=2,
                    blank_reason=BlankPageReason.TECHNICAL,
                ),
            ],
            period_end_capacities=[
                PeriodEndCapacity(
                    year=2025,
                    month=3,
                    unused_photo_slots=3,
                )
            ],
        ),
        print_diagnostic=PrintDiagnostic(
            page_count=4,
            compatible=True,
            pages_to_add=0,
        ),
    )


def test_plan_widget_starts_empty():
    widget = create_widget()

    assert (
        widget._summary_label.text()
        == "No album plan available."
    )

    assert widget._tree.topLevelItemCount() == 0


def test_plan_widget_displays_summary():
    widget = create_widget()

    widget.set_result(create_result())

    text = widget._summary_label.text()

    assert "Pages: 4" in text
    assert "Photo pages: 1" in text
    assert "Dividers: 1" in text
    assert "Special pages: 1" in text
    assert "Technical blanks: 1" in text


def test_plan_widget_displays_no_print_constraint():
    widget = create_widget()

    widget.set_result(create_result())

    assert (
        "no page-count constraint enabled"
        in widget._print_label.text()
    )

def test_plan_widget_displays_print_compatibility():
    widget = create_widget()

    result = create_result()

    constrained_result = AlbumBuildResult(
        plan=result.plan,
        pagination=result.pagination,
        print_diagnostic=PrintDiagnostic(
            page_count=4,
            compatible=True,
            pages_to_add=0,
            page_multiple=4,
        ),
    )

    widget.set_result(constrained_result)

    assert "multiple of 4" in widget._print_label.text()

def test_plan_widget_displays_print_warning():
    widget = create_widget()

    result = create_result()

    constrained_result = AlbumBuildResult(
        plan=result.plan,
        pagination=result.pagination,
        print_diagnostic=PrintDiagnostic(
            page_count=6,
            compatible=False,
            pages_to_add=2,
            page_multiple=4,
        ),
    )

    widget.set_result(constrained_result)

    text = widget._print_label.text()

    assert "not a multiple of 4" in text
    assert "2 additional page(s)" in text

def test_plan_widget_displays_period_suggestion():
    widget = create_widget()

    widget.set_result(create_result())

    text = widget._suggestions_label.text()

    month_name = calendar.month_name[3]

    assert f"{month_name} 2025" in text
    assert "3 additional photo(s)" in text


def test_plan_widget_groups_pages_by_year_and_month():
    widget = create_widget()

    widget.set_result(create_result())

    labels = [
        widget._tree.topLevelItem(index).text(0)
        for index in range(
            widget._tree.topLevelItemCount()
        )
    ]

    assert "2025" in labels
    assert "Other pages" in labels


def test_month_group_contains_page_details():
    widget = create_widget()

    widget.set_result(create_result())

    year_item = next(
        widget._tree.topLevelItem(index)
        for index in range(
            widget._tree.topLevelItemCount()
        )
        if (
            widget._tree.topLevelItem(index).text(0)
            == "2025"
        )
    )

    month_name = calendar.month_name[3]

    march = next(
        year_item.child(index)
        for index in range(
            year_item.childCount()
        )
        if (
            year_item.child(index).text(0)
            == month_name
        )
    )

    assert march.text(1) == "3"

    page_labels = [
        march.child(index).text(0)
        for index in range(
            march.childCount()
        )
    ]

    assert "Page 2 — Month divider" in page_labels
    assert "Page 3 — Photos" in page_labels
    assert "Page 4 — Technical blank" in page_labels


def test_plan_widget_clear_removes_previous_result():
    widget = create_widget()

    widget.set_result(create_result())
    widget.clear()

    assert (
        widget._summary_label.text()
        == "No album plan available."
    )

    assert widget._tree.topLevelItemCount() == 0