from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ScanProgressPhase(str, Enum):
    METADATA = "metadata"
    NOMINATIM = "nominatim"


@dataclass(frozen=True)
class ScanProgress:
    phase: ScanProgressPhase
    current: int
    total: int
