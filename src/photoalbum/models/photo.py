from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from .location_component import LocationComponent


class DateSource(str, Enum):
    EXIF = "exif"
    FILENAME = "filename"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class LocationSource(str, Enum):
    GEOCODING = "geocoding"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass
class Photo:
    path: Path
    filename: str

    file_size: int | None = None
    modified_time_ns: int | None = None
    content_hash: str | None = None

    width: int | None = None
    height: int | None = None

    # Effective metadata used by the album.
    orientation: int | None = None
    capture_datetime: datetime | None = None
    date_source: DateSource = DateSource.UNKNOWN
    latitude: float | None = None
    longitude: float | None = None

    # Metadata originally detected from the source file.
    # These values are preserved when the user applies
    # manual corrections.
    original_orientation: int | None = None
    original_capture_datetime: datetime | None = None
    original_date_source: DateSource = DateSource.UNKNOWN
    original_latitude: float | None = None
    original_longitude: float | None = None

    place_name: str | None = None
    city: str | None = None
    address: str | None = None
    raw_location_data: dict[str, object] | None = None
    location_source: LocationSource = LocationSource.UNKNOWN

    # Editorial geographic information used to describe where the
    # photo was taken.
    selected_location_components: tuple[LocationComponent, ...] = ()
    location_text: str | None = None

    # Free editorial caption, independent from the geographic location.
    caption: str | None = None

    @property
    def has_capture_datetime(self) -> bool:
        return self.capture_datetime is not None

    @property
    def has_gps(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def is_date_anomaly(self) -> bool:
        return not self.has_capture_datetime
