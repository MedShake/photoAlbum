from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class LocationCandidatePriority(IntEnum):
    PLACE = 1
    ROAD = 2
    LOCAL_CONTEXT = 3
    LOCALITY = 4
    ADMINISTRATIVE = 5
    POSTAL = 6
    COUNTRY = 7
    OTHER = 100


@dataclass(frozen=True)
class LocationCandidate:
    key: str
    value: str
    priority: LocationCandidatePriority
