"""Temporal levels actually represented by dividers around a rendered page."""
from photoalbum.album.planning import PlanItemKind


def materialized_periods(page, album_pages) -> frozenset[PlanItemKind]:
    if page is None:
        return frozenset()
    return frozenset(
        candidate.kind for candidate in album_pages
        if candidate.year == getattr(page, "year", None)
        and (candidate.kind == PlanItemKind.YEAR_DIVIDER or (
            candidate.kind == PlanItemKind.MONTH_DIVIDER
            and candidate.month == getattr(page, "month", None)
        ))
    )
