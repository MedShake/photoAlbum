from PySide6.QtWidgets import QApplication

from photoalbum.album import (
    AlbumBuildResult,
    AlbumPlan,
    AlbumStructureSettings,
    BlankPageReason,
    CoverPosition,
    CoverSettings,
    DividerSettings,
    PageInstance,
    PageSide,
    PaginationResult,
    PeriodEndCapacity,
    PlanItemKind,
    PlannedPage,
    PhotoPageSettings,
    PrintDiagnostic,
)
from photoalbum.template_engine import create_template_registry

from photoalbum.gui.widgets import AlbumPlanWidget
from photoalbum.i18n import Translator


def test_excluded_special_page_warnings_follow_build_result(monkeypatch):
    from dataclasses import replace
    from photoalbum.album import AlbumBuilder, PageInstance, TemplateDefinition
    from photoalbum.gui.widgets import AlbumSettingsWidget
    from photoalbum.gui.template_labels import template_display_name

    app = QApplication.instance() or QApplication([])
    registry = create_template_registry()
    editor = AlbumSettingsWidget(registry)
    first = PageInstance(template_id="calendar-index")
    second = PageInstance(template_id="calendar-index", settings={"calendar_index": {"show_title": False}})
    settings = replace(editor.settings(), front_matter=[first], back_matter=[second])
    builder = AlbumBuilder(registry)
    for language in ("fr", "en"):
        widget = AlbumPlanWidget(registry, translator=Translator(language))
        for width, height, excluded in [
            (179.0, 180.0, (first, second)),
            (180.0, 180.0, ()),
        ]:
            current = replace(
                settings,
                page_format="custom",
                custom_width_mm=width,
                custom_height_mm=height,
            )
            result = builder.build([], current)
            assert result.excluded_special_pages == excluded
            # The Plan must consume the diagnostic, never reevaluate geometry.
            with monkeypatch.context() as patch:
                def unexpected_check(*args):
                    raise AssertionError("Plan must not check compatibility")
                patch.setattr(TemplateDefinition, "is_compatible_with_page", unexpected_check)
                widget.set_result(result, current)
            lines = widget._warnings_label.text().splitlines()
            assert len(lines) == len(excluded)
            if excluded:
                name = template_display_name(registry.get(first.template_id), Translator(language))
                assert all(name in line for line in lines)
                assert not widget._warnings_group.isHidden()
            else:
                assert widget._warnings_group.isHidden()
        widget.close()
    assert settings.front_matter == [first] and settings.back_matter == [second]
    editor.close()


def create_widget() -> AlbumPlanWidget:
    application = QApplication.instance()

    if application is None:
        QApplication([])

    return AlbumPlanWidget(
        create_template_registry(),
        translator=Translator("en"),
    )


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


def create_structure_settings() -> AlbumStructureSettings:
    return AlbumStructureSettings(
        covers={
            position: CoverSettings(
                position=position,
                template_id=f"{position.value}-template",
            )
            for position in CoverPosition
        },
        day_dividers=DividerSettings(enabled=False, template_id="day-divider-simple"),
        month_dividers=DividerSettings(
            enabled=True,
            template_id="month-divider-classic",
        ),
        year_dividers=DividerSettings(
            enabled=True,
            template_id="year-divider-classic",
        ),
        photo_pages=PhotoPageSettings(
            template_id="photo-page-2",
        ),
    )


def result_with_pages(pages: list[PlannedPage]) -> AlbumBuildResult:
    return AlbumBuildResult(
        plan=AlbumPlan(),
        pagination=PaginationResult(pages=pages),
        print_diagnostic=PrintDiagnostic(
            page_count=len(pages),
            compatible=True,
            pages_to_add=0,
        ),
    )


def page_numbers_in_visual_order(item) -> list[int]:
    numbers = []
    # Production does not currently attach PlannedPage (or a dedicated role)
    # to the item. A real page is nevertheless the only leaf whose page-count
    # column is exactly 1; covers use an em dash and structural nodes have
    # children. Only the number extraction remains tied to the rendered label.
    if item.childCount() == 0 and item.text(1) == "1":
        number_label = item.text(0).split(" — ", 1)[0]
        numbers.append(int(number_label.rsplit(" ", 1)[1]))
    for index in range(item.childCount()):
        numbers.extend(page_numbers_in_visual_order(item.child(index)))
    return numbers


def structure_labels(item) -> list[str]:
    labels = [item.text(0)]
    for index in range(item.childCount()):
        labels.extend(structure_labels(item.child(index)))
    return labels


def test_unscoped_technical_blank_keeps_physical_position_in_album_body():
    widget = create_widget()
    result = result_with_pages(
        [
            PlannedPage(
                number=1,
                side=PageSide.RIGHT,
                kind=PlanItemKind.YEAR_DIVIDER,
                template_id="year-divider-classic",
                year=2025,
            ),
            PlannedPage(
                number=2,
                side=PageSide.LEFT,
                kind=None,
                template_id=None,
                blank_reason=BlankPageReason.TECHNICAL,
            ),
            PlannedPage(
                number=3,
                side=PageSide.RIGHT,
                kind=PlanItemKind.MONTH_DIVIDER,
                template_id="month-divider-classic",
                year=2025,
                month=3,
            ),
        ]
    )

    widget.set_result(result, create_structure_settings())

    body = next(
        widget._tree.topLevelItem(index)
        for index in range(widget._tree.topLevelItemCount())
        if widget._tree.topLevelItem(index).text(0) == "Album body"
    )
    year = next(
        body.child(index)
        for index in range(body.childCount())
        if body.child(index).text(0) == "2025"
    )

    assert [
        year.child(index).text(0)
        for index in range(year.childCount())
    ] == [
        "Page 1 — Year divider",
        "Page 2 — Technical blank",
        "March",
    ]
    assert all(
        body.child(index).text(0) != "Other pages"
        for index in range(body.childCount())
    )
    widget.close()


def test_unscoped_page_without_shared_context_stays_in_physical_position():
    widget = create_widget()
    result = result_with_pages(
        [
            PlannedPage(
                number=1,
                side=PageSide.RIGHT,
                kind=None,
                template_id=None,
                blank_reason=BlankPageReason.TECHNICAL,
            ),
            PlannedPage(
                number=2,
                side=PageSide.LEFT,
                kind=PlanItemKind.YEAR_DIVIDER,
                template_id="year-divider-classic",
                year=2025,
            ),
        ]
    )

    widget.set_result(result, create_structure_settings())

    body = next(
        widget._tree.topLevelItem(index)
        for index in range(widget._tree.topLevelItemCount())
        if widget._tree.topLevelItem(index).text(0) == "Album body"
    )
    assert [
        body.child(index).text(0)
        for index in range(body.childCount())
    ] == [
        "Page 1 — Technical blank",
        "2025",
    ]
    widget.close()


def test_structured_plan_recursive_page_order_matches_physical_document():
    widget = create_widget()
    settings = create_structure_settings()
    front = PageInstance(template_id="calendar-index")
    back = PageInstance(template_id="calendar-index")
    settings.front_matter = [front]
    settings.back_matter = [back]
    pages = [
        PlannedPage(1, PageSide.RIGHT, PlanItemKind.SPECIAL_PAGE,
                    "calendar-index", page_instance=front),
        PlannedPage(2, PageSide.LEFT, None, None,
                    blank_reason=BlankPageReason.TECHNICAL),
        PlannedPage(3, PageSide.RIGHT, PlanItemKind.YEAR_DIVIDER,
                    "year-divider-classic", year=2025),
        PlannedPage(4, PageSide.LEFT, PlanItemKind.MONTH_DIVIDER,
                    "month-divider-classic", year=2025, month=3),
        PlannedPage(5, PageSide.RIGHT, None, None,
                    blank_reason=BlankPageReason.EDITORIAL),
        PlannedPage(6, PageSide.LEFT, PlanItemKind.PHOTO_GROUP,
                    "photo-page-2", year=2025, month=3),
        PlannedPage(7, PageSide.RIGHT, None, None,
                    blank_reason=BlankPageReason.TECHNICAL),
        PlannedPage(8, PageSide.LEFT, PlanItemKind.MONTH_DIVIDER,
                    "month-divider-classic", year=2025, month=4),
        PlannedPage(9, PageSide.RIGHT, None, None,
                    blank_reason=BlankPageReason.TECHNICAL),
        PlannedPage(10, PageSide.LEFT, PlanItemKind.SPECIAL_PAGE,
                    "calendar-index", page_instance=back),
    ]

    widget.set_result(result_with_pages(pages), settings)

    numbers = []
    labels = []
    for index in range(widget._tree.topLevelItemCount()):
        item = widget._tree.topLevelItem(index)
        numbers.extend(page_numbers_in_visual_order(item))
        labels.extend(structure_labels(item))

    assert numbers == list(range(1, 11))
    assert "Other pages" not in labels
    assert [
        widget._tree.topLevelItem(index).text(0)
        for index in range(widget._tree.topLevelItemCount())
    ] == [
        "Front cover:",
        "Inside front cover:",
        "Special pages after inside front cover",
        "Album body",
        "Special pages before inside back cover",
        "Inside back cover:",
        "Back cover:",
    ]
    widget.close()


def test_reentering_period_creates_new_groups_instead_of_reordering_pages():
    widget = create_widget()
    pages = [
        PlannedPage(1, PageSide.RIGHT, PlanItemKind.PHOTO_GROUP,
                    "photo-page-2", year=2025, month=3),
        PlannedPage(2, PageSide.LEFT, None, None,
                    blank_reason=BlankPageReason.TECHNICAL),
        PlannedPage(3, PageSide.RIGHT, PlanItemKind.PHOTO_GROUP,
                    "photo-page-2", year=2026, month=4),
        PlannedPage(4, PageSide.LEFT, PlanItemKind.PHOTO_GROUP,
                    "photo-page-2", year=2025, month=3),
    ]

    widget.set_result(result_with_pages(pages), create_structure_settings())

    body = next(
        widget._tree.topLevelItem(index)
        for index in range(widget._tree.topLevelItemCount())
        if widget._tree.topLevelItem(index).text(0) == "Album body"
    )
    assert [
        body.child(index).text(0)
        for index in range(body.childCount())
    ] == [
        "2025",
        "Page 2 — Technical blank",
        "2026",
        "2025",
    ]

    first_2025 = body.child(0)
    second_2025 = body.child(3)
    assert first_2025.childCount() == 1
    assert second_2025.childCount() == 1
    assert first_2025.child(0).text(0) == "March"
    assert second_2025.child(0).text(0) == "March"
    assert page_numbers_in_visual_order(body) == [1, 2, 3, 4]
    widget.close()


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

    # Summary displays the complete physical document:
    # four interior pages + four cover pages.
    assert "Pages: 8" in text
    assert "Photo pages: 1" in text
    assert "Dividers: 1" in text
    assert "Special pages: 1" in text
    assert "Technical blanks: 1" in text



def test_plan_widget_hides_warnings_without_print_constraint():
    widget = create_widget()

    widget.set_result(create_result())

    assert widget._warnings_label.text() == ""
    assert not widget._warnings_group.isVisible()



def test_plan_widget_hides_warnings_when_print_is_compatible():
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

    assert widget._warnings_label.text() == ""
    assert not widget._warnings_group.isVisible()



def test_plan_widget_displays_incompatible_print_as_warning():
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

    text = widget._warnings_label.text()

    assert "multiple of 4" in text
    assert "2 additional pages" in text
    assert "page(s)" not in text
    assert not widget._warnings_group.isHidden()



def test_plan_widget_displays_period_suggestion():
    widget = create_widget()

    widget.set_result(create_result())

    text = widget._suggestions_label.text()

    assert "March 2025" in text
    assert "Optimization —" not in text
    assert "3 additional photos" in text
    assert not widget._optimizations_group.isHidden()


def test_plan_widget_groups_pages_by_year_and_month():
    widget = create_widget()

    widget.set_result(create_result())

    labels = [
        widget._tree.topLevelItem(index).text(0)
        for index in range(
            widget._tree.topLevelItemCount()
        )
    ]

    assert labels == [
        "Page 1 — Special page",
        "2025",
    ]


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

    march = next(
        year_item.child(index)
        for index in range(
            year_item.childCount()
        )
        if (
            year_item.child(index).text(0)
            == "March"
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


def test_plan_cover_template_name_includes_pack_name():
    widget = create_widget()

    name = widget._template_name(
        "year-photo-scatter"
    )

    assert name.startswith("MSB — ")


def test_empty_caption_diagnostics_are_not_recomputed(monkeypatch):
    from unittest.mock import Mock
    widget = create_widget()
    collect = Mock(return_value={})
    monkeypatch.setattr(widget, "_collect_caption_overflows", collect)
    widget.set_result(create_result())
    assert collect.call_count == 1
    widget.close()


def test_day_groups_follow_pagination_inside_each_month():
    from dataclasses import replace
    from datetime import datetime
    from pathlib import Path
    from photoalbum.album import AlbumBuilder, DividerPlacement
    from photoalbum.gui.widgets import AlbumSettingsWidget
    from photoalbum.models import Photo

    widget = create_widget()
    editor = AlbumSettingsWidget(create_template_registry())
    settings = editor.settings()
    settings.day_dividers = replace(settings.day_dividers, enabled=True,
                                    placement=DividerPlacement.NATURAL)
    settings.month_dividers = replace(settings.month_dividers, placement=DividerPlacement.NATURAL)
    settings.year_dividers = replace(settings.year_dividers, placement=DividerPlacement.NATURAL)
    # Deliberately unsorted input; the tree consumes the planner's order.
    dates = [(4, 10), (3, 12), (3, 2), (4, 2), (3, 2), (3, 2)]
    photos = [Photo(path=Path(f"{i}.jpg"), filename=f"{i}.jpg",
                    capture_datetime=datetime(2025, month, day))
              for i, (month, day) in enumerate(dates)]
    result = AlbumBuilder(create_template_registry()).build(photos, settings)
    widget.set_result(result, settings)
    body = next(widget._tree.topLevelItem(i) for i in range(widget._tree.topLevelItemCount())
                if widget._tree.topLevelItem(i).text(0) == "Album body")
    year = body.child(0)
    months = [year.child(i) for i in range(year.childCount()) if year.child(i).childCount()]
    assert [item.text(0) for item in months] == ["March", "April"]
    for month_number, month, expected_days in zip((3, 4), months, ([2, 12], [2, 10])):
        # The monthly separator stays directly under its month.
        assert "Month divider" in month.child(0).text(0)
        days = [month.child(i) for i in range(1, month.childCount())]
        expected_labels = {
            3: ["2  Sunday", "12  Wednesday"],
            4: ["2  Wednesday", "10  Thursday"],
        }
        assert [day.text(0) for day in days] == expected_labels[month_number]
        for day_number, day in zip(expected_days, days):
            pages = [p for p in result.pagination.pages
                     if (p.year, p.month, p.day) == (2025, month_number, day_number)]
            assert page_numbers_in_visual_order(day) == [p.number for p in pages]
            assert "Day divider" in day.child(0).text(0)
            assert all("Photos" in day.child(i).text(0) for i in range(1, day.childCount()))
            assert int(day.text(1)) == len(pages)
            assert int(day.text(2)) == sum(len(p.photos) for p in pages)
            assert day.isExpanded()
            widget._tree.collapseItem(day)
            assert not day.isExpanded()
            assert month.isExpanded()
            widget._tree.expandItem(day)
            assert day.isExpanded()
            assert page_numbers_in_visual_order(day) == [p.number for p in pages]
    assert page_numbers_in_visual_order(body) == [p.number for p in result.pagination.pages]
    # Even with dated pagination, the setting alone controls the extra level.
    settings.day_dividers = replace(settings.day_dividers, enabled=False)
    widget.set_result(result, settings)
    body = next(widget._tree.topLevelItem(i) for i in range(widget._tree.topLevelItemCount())
                if widget._tree.topLevelItem(i).text(0) == "Album body")
    year = body.child(0)
    months = [year.child(i) for i in range(year.childCount()) if year.child(i).childCount()]
    assert all(month.child(i).childCount() == 0 for month in months for i in range(month.childCount()))
    assert page_numbers_in_visual_order(body) == [p.number for p in result.pagination.pages]
    editor.close()
    widget.close()


def test_day_groups_keep_unscoped_pages_and_reentered_dates_in_physical_order():
    from dataclasses import replace

    widget = create_widget()
    settings = create_structure_settings()
    settings.day_dividers = replace(settings.day_dividers, enabled=True)
    pages = [
        PlannedPage(1, PageSide.RIGHT, PlanItemKind.DAY_DIVIDER, "day-divider-simple",
                    year=2025, month=3, day=2),
        PlannedPage(2, PageSide.LEFT, PlanItemKind.PHOTO_GROUP, "photo-page-2",
                    year=2025, month=3, day=2),
        PlannedPage(3, PageSide.RIGHT, None, None, year=2025, month=3,
                    blank_reason=BlankPageReason.TECHNICAL),
        PlannedPage(4, PageSide.LEFT, PlanItemKind.DAY_DIVIDER, "day-divider-simple",
                    year=2025, month=3, day=12),
        PlannedPage(5, PageSide.RIGHT, PlanItemKind.PHOTO_GROUP, "photo-page-2",
                    year=2025, month=3, day=2),
    ]
    widget.set_result(result_with_pages(pages), settings)
    body = next(widget._tree.topLevelItem(i) for i in range(widget._tree.topLevelItemCount())
                if widget._tree.topLevelItem(i).text(0) == "Album body")
    march = body.child(0).child(0)
    assert [march.child(i).text(0) for i in range(march.childCount())] == [
        "2  Sunday", "Page 3 — Technical blank", "12  Wednesday", "2  Sunday",
    ]
    assert page_numbers_in_visual_order(body) == [1, 2, 3, 4, 5]
    widget.close()


def test_day_group_weekday_uses_application_language():
    from dataclasses import replace
    from PySide6.QtCore import QLocale

    app = QApplication.instance() or QApplication([])
    settings = create_structure_settings()
    settings.day_dividers = replace(settings.day_dividers, enabled=True)
    result = result_with_pages([
        PlannedPage(1, PageSide.RIGHT, PlanItemKind.DAY_DIVIDER, "day-divider-simple",
                    year=2025, month=10, day=17),
    ])
    previous_locale = QLocale()
    try:
        # The application language, not Qt's default locale, determines the label.
        QLocale.setDefault(QLocale("de_DE"))
        for language, expected in [("fr", "17  Vendredi"), ("en", "17  Friday")]:
            widget = AlbumPlanWidget(create_template_registry(), translator=Translator(language))
            try:
                widget.set_result(result, settings)
                labels = [label for i in range(widget._tree.topLevelItemCount())
                          for label in structure_labels(widget._tree.topLevelItem(i))]
                assert expected in labels
            finally:
                widget.close()
    finally:
        QLocale.setDefault(previous_locale)
