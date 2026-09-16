from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ProcessingEventType(str, Enum):
    ANALYSIS_STARTED = "analysis_started"
    DATE_FROM_EXIF = "date_from_exif"
    DATE_FROM_FILENAME = "date_from_filename"
    DATE_MISSING = "date_missing"
    GPS_FOUND = "gps_found"
    GPS_MISSING = "gps_missing"
    GEOCODING_STARTED = "geocoding_started"
    LOCATION_FROM_CACHE = "location_from_cache"
    LOCATION_FROM_REVERSE = "location_from_reverse"
    LOCATION_NOT_FOUND = "location_not_found"
    ANALYSIS_COMPLETED = "analysis_completed"
    GEOCODING_ERROR = "geocoding_error"


@dataclass(frozen=True)
class ProcessingEvent:
    type: ProcessingEventType
    path: Path
    message: str

