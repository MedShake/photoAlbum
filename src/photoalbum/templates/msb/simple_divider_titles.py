"""Editorial title choices shared by MSB's two simple separators."""
from datetime import date

from photoalbum.template_engine.api import PlanItemKind, format_date_parts

FORMATS = {
    "month": ("month", "month_year"),
    "day": ("weekday_day", "weekday_day_month", "full_date"),
}


def automatic_format(kind, context):
    if kind == "month":
        return "month" if PlanItemKind.YEAR_DIVIDER in context else "month_year"
    if PlanItemKind.MONTH_DIVIDER in context:
        return "weekday_day"
    return "weekday_day_month" if PlanItemKind.YEAR_DIVIDER in context else "full_date"


def divider_title(kind, page, settings, translator, context=()):
    selected = settings.get(f"{kind}_divider_simple", {}).get("title_format", "auto")
    if selected not in FORMATS[kind]:
        selected = automatic_format(kind, context)
    return format_date_parts(
        date(page.year or 2000, page.month, getattr(page, "day", None) or 1),
        language=translator.language,
        weekday=kind == "day", day=kind == "day",
        month=selected != "weekday_day",
        year=selected in ("month_year", "full_date") and page.year is not None,
    )
