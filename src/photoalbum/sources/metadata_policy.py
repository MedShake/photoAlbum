from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import json
from photoalbum.models.coordinates import usable_coordinates

from photoalbum.models import (
    DateSource,
    GpsSource,
    LocationSource,
    Photo,
)


_VALID_DATE_PREFERENCES = {
    "exif",
    "source",
    "filename",
}

_VALID_GPS_PREFERENCES = {
    "exif",
    "source",
}

_VALID_LOCATION_PREFERENCES = {
    "source",
    "geocoding",
    "none",
}


@dataclass(frozen=True)
class PhotoMetadataPolicy:
    """Source-level defaults for choosing effective photo metadata."""

    date_preference: str
    gps_preference: str
    location_preference: str
    nominatim_enabled: bool
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(
                f"Unsupported photo metadata policy schema: "
                f"{self.schema_version}"
            )

        if self.date_preference not in _VALID_DATE_PREFERENCES:
            raise ValueError(
                f"Unsupported date preference: {self.date_preference}"
            )

        if self.gps_preference not in _VALID_GPS_PREFERENCES:
            raise ValueError(
                f"Unsupported GPS preference: {self.gps_preference}"
            )

        if self.location_preference not in _VALID_LOCATION_PREFERENCES:
            raise ValueError(
                f"Unsupported location preference: "
                f"{self.location_preference}"
            )

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "date_preference": self.date_preference,
                "gps_preference": self.gps_preference,
                "location_preference": self.location_preference,
                "nominatim_enabled": self.nominatim_enabled,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str) -> "PhotoMetadataPolicy":
        data = json.loads(value)

        if not isinstance(data, dict):
            raise ValueError("Photo metadata policy must be a JSON object.")

        return cls(
            schema_version=int(data.get("schema_version", 0)),
            date_preference=str(data["date_preference"]),
            gps_preference=str(data["gps_preference"]),
            location_preference=str(data["location_preference"]),
            nominatim_enabled=bool(data["nominatim_enabled"]),
        )

    @classmethod
    def for_source_kind(cls, kind: str) -> "PhotoMetadataPolicy":
        if kind == "local":
            return cls(
                date_preference="exif",
                gps_preference="exif",
                location_preference="none",
                nominatim_enabled=False,
            )

        return cls(
            date_preference="source",
            gps_preference="source",
            location_preference="source",
            nominatim_enabled=False,
        )


def resolve_photo_metadata(
    photo: Photo,
    policy: PhotoMetadataPolicy,
) -> Photo:
    """Resolve effective metadata without altering stored candidates.

    Manual effective values always win. Automatic preferences use the
    requested candidate first, then a conservative fallback when that
    candidate is unavailable.
    """
    resolved = replace(photo)

    _resolve_date(resolved, policy)
    _resolve_gps(resolved, policy)
    _resolve_location(resolved, policy)

    return resolved


def _resolve_date(
    photo: Photo,
    policy: PhotoMetadataPolicy,
) -> None:
    manual = photo.manual_capture_datetime
    if manual is None and photo.date_source == DateSource.MANUAL:
        manual = photo.capture_datetime
    if manual is not None:
        photo.capture_datetime = manual
        photo.date_source = DateSource.MANUAL
        return

    candidates = {
        "exif": (
            photo.exif_capture_datetime,
            DateSource.EXIF,
        ),
        "source": (
            photo.source_capture_datetime,
            DateSource.SOURCE,
        ),
        "filename": (
            _filename_capture_datetime(photo),
            DateSource.FILENAME,
        ),
    }
    for key, value in photo.metadata_candidates.date.items():
        candidates[_policy_key(key)] = (
            value,
            _date_provenance(key),
        )

    fallback_order = {
        "exif": ("exif", "source", "filename"),
        "source": ("source", "exif", "filename"),
        "filename": ("filename", "exif", "source"),
    }

    for name in fallback_order[policy.date_preference]:
        value, provenance = candidates[name]
        if value is not None:
            photo.capture_datetime = value
            photo.date_source = provenance
            return

    photo.capture_datetime = None
    photo.date_source = DateSource.UNKNOWN


def _filename_capture_datetime(photo: Photo) -> datetime | None:
    if photo.original_date_source == DateSource.FILENAME:
        return photo.original_capture_datetime
    return None


def _resolve_gps(
    photo: Photo,
    policy: PhotoMetadataPolicy,
) -> None:
    manual_latitude = photo.manual_latitude
    manual_longitude = photo.manual_longitude
    if (
        manual_latitude is None
        and manual_longitude is None
        and photo.gps_source == GpsSource.MANUAL
    ):
        manual_latitude = photo.latitude
        manual_longitude = photo.longitude
        if manual_latitude is None and manual_longitude is None:
            return
    if usable_coordinates(manual_latitude, manual_longitude):
        photo.latitude = manual_latitude
        photo.longitude = manual_longitude
        photo.gps_source = GpsSource.MANUAL
        return

    candidates = {
        "exif": (
            photo.exif_latitude,
            photo.exif_longitude,
            GpsSource.EXIF,
        ),
        "source": (
            photo.source_latitude,
            photo.source_longitude,
            GpsSource.SOURCE,
        ),
    }
    for key, value in photo.metadata_candidates.gps.items():
        candidates[_policy_key(key)] = (
            value.latitude,
            value.longitude,
            _gps_provenance(key),
        )

    fallback_order = (
        ("exif", "source")
        if policy.gps_preference == "exif"
        else ("source", "exif")
    )

    for name in fallback_order:
        latitude, longitude, provenance = candidates[name]
        if usable_coordinates(latitude, longitude):
            photo.latitude = latitude
            photo.longitude = longitude
            photo.gps_source = provenance
            return

    photo.latitude = None
    photo.longitude = None
    photo.gps_source = GpsSource.UNKNOWN


def _resolve_location(
    photo: Photo,
    policy: PhotoMetadataPolicy,
) -> None:
    manual = photo.manual_location_data
    source_candidate = _usable_location_candidate(
        photo.source_location_data
        or photo.metadata_candidates.location.get("provider")
    )
    geocoded_candidate = _usable_geocoded_candidate(photo)

    # The Places widget stores a per-photo source choice inside the existing
    # extensible editorial JSON. It takes precedence over the project policy,
    # while the policy remains the default when no local choice exists.
    override_origin = None
    if isinstance(manual, dict):
        state = manual.get("photo_places")
        if isinstance(state, dict):
            value = state.get("origin")
            if value in {"provider", "geocoding", "manual", "none"}:
                override_origin = str(value)

    if override_origin == "provider":
        if source_candidate is not None:
            _apply_location_candidate(
                photo, source_candidate, LocationSource.SOURCE
            )
        else:
            _clear_effective_location(photo)
        return
    if override_origin == "geocoding":
        if geocoded_candidate is not None:
            _apply_location_candidate(
                photo, geocoded_candidate, LocationSource.GEOCODING
            )
        else:
            _clear_effective_location(photo)
        return
    if override_origin == "none":
        _clear_effective_location(photo)
        return
    if override_origin == "manual":
        manual_candidate = _usable_location_candidate(manual)
        if manual_candidate is None and isinstance(manual, dict):
            state = manual.get("photo_places")
            if isinstance(state, dict):
                manual_candidate = _usable_location_candidate(
                    state.get("manual_data")
                    if isinstance(state.get("manual_data"), dict)
                    else None
                )
        if manual_candidate is not None:
            _apply_location_candidate(
                photo, manual_candidate, LocationSource.MANUAL
            )
        else:
            _clear_effective_location(photo)
            photo.location_source = LocationSource.MANUAL
        return

    # Existing manual state remains authoritative. This also preserves the
    # explicit "manual GPS, location not resolved yet" state.
    if manual is None and photo.location_source == LocationSource.MANUAL:
        manual = {
            "place_name": photo.place_name,
            "city": photo.city,
            "address": photo.address,
            "raw": photo.raw_location_data,
        }
    if _usable_location_candidate(manual) is not None:
        _apply_location_candidate(photo, manual, LocationSource.MANUAL)
        return
    if photo.location_source == LocationSource.MANUAL:
        return

    if policy.location_preference == "none":
        _clear_effective_location(photo)
        return

    if policy.location_preference == "source":
        candidates = (
            (source_candidate, LocationSource.SOURCE),
            (geocoded_candidate, LocationSource.GEOCODING),
        )
    else:
        candidates = (
            (geocoded_candidate, LocationSource.GEOCODING),
            (source_candidate, LocationSource.SOURCE),
        )

    for candidate, provenance in candidates:
        if candidate is None:
            continue

        _apply_location_candidate(photo, candidate, provenance)
        return

    _clear_effective_location(photo)


def _usable_location_candidate(
    value: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None

    if any(
        _optional_text(value.get(key)) is not None
        for key in ("place_name", "city", "address")
    ):
        return value

    components = value.get("components")
    if isinstance(components, list) and components:
        return value

    raw = value.get("raw")
    if isinstance(raw, dict) and raw:
        return value

    return None


def _usable_geocoded_candidate(
    photo: Photo,
) -> dict[str, object] | None:
    candidate = _usable_location_candidate(
        photo.geocoded_location_data
        or photo.metadata_candidates.location.get("geocoding")
    )
    if candidate is None:
        return None

    if photo.latitude is None or photo.longitude is None:
        return None

    latitude = candidate.get("latitude")
    longitude = candidate.get("longitude")

    if not isinstance(latitude, (int, float)):
        return None
    if not isinstance(longitude, (int, float)):
        return None

    if not _coordinates_match(
        photo.latitude,
        photo.longitude,
        float(latitude),
        float(longitude),
    ):
        return None

    return candidate


def _coordinates_match(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> bool:
    tolerance = 1e-7
    return (
        abs(first_latitude - second_latitude) <= tolerance
        and abs(first_longitude - second_longitude) <= tolerance
    )


def _clear_effective_location(photo: Photo) -> None:
    photo.place_name = None
    photo.city = None
    photo.address = None
    photo.raw_location_data = None
    photo.location_source = LocationSource.UNKNOWN


def _apply_location_candidate(
    photo: Photo,
    candidate: dict[str, object],
    provenance: LocationSource,
) -> None:
    photo.place_name = _optional_text(candidate.get("place_name"))
    photo.city = _optional_text(candidate.get("city"))
    photo.address = _optional_text(candidate.get("address"))
    raw = candidate.get("raw")
    components = candidate.get("components")
    if isinstance(raw, dict) and isinstance(raw.get("address"), dict):
        photo.raw_location_data = dict(raw)
    elif isinstance(components, list):
        address_data = {
            str(item["key"]): str(item["value"])
            for item in components
            if isinstance(item, dict) and item.get("key") and item.get("value")
        }
        photo.raw_location_data = {"address": address_data}
    elif isinstance(raw, dict):
        photo.raw_location_data = {"address": dict(raw)}
    else:
        photo.raw_location_data = None
    photo.location_source = provenance


def _policy_key(key: str) -> str:
    return "source" if key == "provider" else key


def _date_provenance(key: str) -> DateSource:
    return {
        "provider": DateSource.SOURCE,
        "source": DateSource.SOURCE,
        "exif": DateSource.EXIF,
        "filename": DateSource.FILENAME,
    }.get(key, DateSource.UNKNOWN)


def _gps_provenance(key: str) -> GpsSource:
    return {
        "provider": GpsSource.SOURCE,
        "source": GpsSource.SOURCE,
        "exif": GpsSource.EXIF,
    }.get(key, GpsSource.UNKNOWN)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None
