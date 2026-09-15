from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class LocationCandidatePriority(IntEnum):
    PLACE = 1
    ROAD = 2
    LOCAL_CONTEXT = 3
    SMALL_LOCALITY = 4
    LOCALITY = 5
    ADMINISTRATIVE = 6
    POSTAL = 7
    COUNTRY = 8
    OTHER = 100


@dataclass(frozen=True)
class LocationCandidate:
    key: str
    value: str
    priority: LocationCandidatePriority
