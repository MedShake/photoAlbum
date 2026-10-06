from types import SimpleNamespace

from photoalbum.album.pagination import PaginationEngine, PaginationResult, PageSide, PlannedPage
from photoalbum.album.planning import PlanItemKind


def _settings(*, day=False, month=False, year=False):
    return SimpleNamespace(
        day_dividers=SimpleNamespace(enabled=day),
        month_dividers=SimpleNamespace(enabled=month),
        year_dividers=SimpleNamespace(enabled=year),
    )


def _page(number, year, month, day, capacity):
    return PlannedPage(
        number=number,
        side=PageSide.RIGHT if number % 2 else PageSide.LEFT,
        kind=PlanItemKind.PHOTO_GROUP,
        template_id="photo",
        year=year,
        month=month,
        day=day,
        photo_capacity=capacity,
    )


def _capacities(settings):
    result = PaginationResult(pages=[
        _page(1, 2025, 3, 1, 1),
        _page(2, 2025, 3, 1, 2),
        _page(3, 2025, 3, 2, 3),
        _page(4, 2025, 4, 1, 4),
        _page(5, 2026, 1, 1, 5),
    ])
    engine = PaginationEngine.__new__(PaginationEngine)
    engine._insertions = {}
    engine._record_period_capacities(result, settings)
    return result.period_end_capacities


def test_no_separator_reports_only_end_of_album():
    values = _capacities(_settings())
    assert [(c.scope, c.year, c.month, c.day, c.unused_photo_slots) for c in values] == [
        ("album", None, None, None, 5),
    ]


def test_year_separator_reports_each_year():
    values = _capacities(_settings(year=True))
    assert [(c.scope, c.year, c.month, c.day, c.unused_photo_slots) for c in values] == [
        ("year", 2025, None, None, 4),
        ("year", 2026, None, None, 5),
    ]


def test_month_separator_takes_priority_over_year():
    values = _capacities(_settings(month=True, year=True))
    assert [(c.scope, c.year, c.month, c.day, c.unused_photo_slots) for c in values] == [
        ("month", 2025, 3, None, 3),
        ("month", 2025, 4, None, 4),
        ("month", 2026, 1, None, 5),
    ]


def test_day_separator_takes_priority_over_month_and_year():
    values = _capacities(_settings(day=True, month=True, year=True))
    assert [(c.scope, c.year, c.month, c.day, c.unused_photo_slots) for c in values] == [
        ("day", 2025, 3, 1, 2),
        ("day", 2025, 3, 2, 3),
        ("day", 2025, 4, 1, 4),
        ("day", 2026, 1, 1, 5),
    ]


def test_day_scope_ignores_photo_pages_without_complete_date():
    result = PaginationResult(pages=[
        _page(1, 2025, 3, 1, 2),
        _page(2, 2025, 3, None, 4),
        _page(3, None, None, None, 6),
    ])
    engine = PaginationEngine.__new__(PaginationEngine)
    engine._insertions = {}

    engine._record_period_capacities(result, _settings(day=True))

    assert [(c.scope, c.year, c.month, c.day, c.unused_photo_slots) for c in result.period_end_capacities] == [
        ("day", 2025, 3, 1, 2),
    ]


def test_month_scope_ignores_photo_pages_without_complete_month():
    result = PaginationResult(pages=[
        _page(1, 2025, 3, None, 2),
        _page(2, 2025, None, None, 4),
        _page(3, None, None, None, 6),
    ])
    engine = PaginationEngine.__new__(PaginationEngine)
    engine._insertions = {}

    engine._record_period_capacities(result, _settings(month=True))

    assert [(c.scope, c.year, c.month, c.day, c.unused_photo_slots) for c in result.period_end_capacities] == [
        ("month", 2025, 3, None, 2),
    ]


def test_year_scope_ignores_photo_pages_without_year():
    result = PaginationResult(pages=[
        _page(1, 2025, None, None, 2),
        _page(2, None, None, None, 6),
    ])
    engine = PaginationEngine.__new__(PaginationEngine)
    engine._insertions = {}

    engine._record_period_capacities(result, _settings(year=True))

    assert [(c.scope, c.year, c.month, c.day, c.unused_photo_slots) for c in result.period_end_capacities] == [
        ("year", 2025, None, None, 2),
    ]


def test_album_scope_still_accepts_undated_photo_pages():
    result = PaginationResult(pages=[
        _page(1, None, None, None, 2),
        _page(2, None, None, None, 6),
    ])
    engine = PaginationEngine.__new__(PaginationEngine)
    engine._insertions = {}

    engine._record_period_capacities(result, _settings())

    assert [(c.scope, c.year, c.month, c.day, c.unused_photo_slots) for c in result.period_end_capacities] == [
        ("album", None, None, None, 6),
    ]
