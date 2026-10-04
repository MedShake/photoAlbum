from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from .location_component import LocationComponent
from .metadata_candidates import MetadataCandidates


class DateSource(str, Enum):
    EXIF = "exif"
    SOURCE = "source"
    FILENAME = "filename"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class GpsSource(str, Enum):
    EXIF = "exif"
    SOURCE = "source"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class LocationSource(str, Enum):
    SOURCE = "source"
    GEOCODING = "geocoding"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass
class Photo:
    # ``path`` is the currently materialized representation of the asset.  It
    # is permanent for local sources and may be absent (or point at a cache
    # entry) for remote sources.  It is deliberately no longer the identity.
    path: Path | None
    filename: str

    source_id: str = "local"
    asset_id: str | None = None
    imported_location_text: str | None = None
    imported_caption: str | None = None
    source_metadata: dict[str, object] | None = None
    metadata_candidates: MetadataCandidates = field(
        default_factory=MetadataCandidates
    )

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
    gps_source: GpsSource = GpsSource.UNKNOWN

    # User-authored values are independent from imported candidates and from
    # the current effective resolution.
    manual_capture_datetime: datetime | None = None
    manual_latitude: float | None = None
    manual_longitude: float | None = None
    manual_location_data: dict[str, object] | None = None

    # Metadata originally detected from the source file.
    # These values are preserved when the user applies
    # manual corrections.
    original_orientation: int | None = None
    original_capture_datetime: datetime | None = None
    original_date_source: DateSource = DateSource.UNKNOWN
    original_latitude: float | None = None
    original_longitude: float | None = None

    # Independent metadata candidates. They are deliberately separate from
    # the effective values above so changing the project policy never destroys
    # information supplied by another source.
    exif_capture_datetime: datetime | None = None
    source_capture_datetime: datetime | None = None
    exif_latitude: float | None = None
    exif_longitude: float | None = None
    source_latitude: float | None = None
    source_longitude: float | None = None

    source_location_data: dict[str, object] | None = None
    geocoded_location_data: dict[str, object] | None = None

    place_name: str | None = None
    city: str | None = None
    address: str | None = None
    raw_location_data: dict[str, object] | None = None
    location_source: LocationSource = LocationSource.UNKNOWN

    # Editorial geographic information used to describe where the
    # photo was taken.
    selected_location_components: tuple[LocationComponent, ...] = ()
    location_text: str | None = None
    location_selection_edited: bool = False

    # Free editorial caption, independent from the geographic location.
    caption: str | None = None

    @property
    def identity(self) -> str:
        """Stable project identity, independent from local materialization."""
        if self.asset_id is not None:
            return f"{self.source_id}:{self.asset_id}"
        if self.path is None:
            raise ValueError("A photo needs either an asset id or a local path.")
        return f"local:{self.path}"

    def require_path(self) -> Path:
        """Return a renderer-ready path or fail with an actionable error."""
        if self.path is None:
            raise FileNotFoundError(
                f"Photo asset is not materialized: {self.identity}"
            )
        return self.path

    @property
    def has_capture_datetime(self) -> bool:
        return self.capture_datetime is not None

    @property
    def has_gps(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def is_date_anomaly(self) -> bool:
        return not self.has_capture_datetime
