from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class DateSource(str, Enum):
    EXIF = "exif"
    FILENAME = "filename"
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
    orientation: int | None = None

    capture_datetime: datetime | None = None
    date_source: DateSource = DateSource.UNKNOWN

    latitude: float | None = None
    longitude: float | None = None

    place_name: str | None = None
    city: str | None = None
    address: str | None = None

    @property
    def has_capture_datetime(self) -> bool:
        return self.capture_datetime is not None

    @property
    def has_gps(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def is_date_anomaly(self) -> bool:
        return not self.has_capture_datetime
        