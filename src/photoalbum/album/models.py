from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CoverPosition(str, Enum):
    FRONT = "front"
    INSIDE_FRONT = "inside_front"
    INSIDE_BACK = "inside_back"
    BACK = "back"


@dataclass(frozen=True)
class PageFormat:
    name: str
    width_mm: float
    height_mm: float


A4 = PageFormat(
    name="A4",
    width_mm=210.0,
    height_mm=297.0,
)


A5 = PageFormat(
    name="A5",
    width_mm=148.0,
    height_mm=210.0,
)


US_LETTER = PageFormat(
    name="US Letter",
    width_mm=215.9,
    height_mm=279.4,
)


@dataclass(frozen=True)
class PrintProfile:
    name: str
    page_format: PageFormat = A4
    target_ppi: int = 300
    bleed_mm: float = 0.0
    safe_margin_mm: float = 10.0
    page_count_multiple: int | None = None