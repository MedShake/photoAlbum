from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuiltinTemplateDefaults:
    front_cover: str
    inside_front_cover: str
    inside_back_cover: str
    back_cover: str
    photo_page: str
    year_divider: str
    month_divider: str


DEFAULT_TEMPLATES = BuiltinTemplateDefaults(
    front_cover="year-photo-scatter",
    inside_front_cover="geographic-word-cloud",
    inside_back_cover="dedication",
    back_cover="geographic-word-cloud",
    photo_page="photo-page-2",
    year_divider="calendar-index",
    month_divider="month-divider-classic",
)
