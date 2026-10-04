from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from collections.abc import Mapping


@dataclass(frozen=True)
class GpsCandidate:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class MetadataCandidates:
    """Provider-neutral metadata advertised for one photo asset.

    Candidate keys describe the origin (``provider``, ``exif``,
    ``filename`` or ``geocoding``), never a concrete product.  The provider
    display identity is carried by the project source instead.
    """

    date: dict[str, datetime] = field(default_factory=dict)
    gps: dict[str, GpsCandidate] = field(default_factory=dict)
    location: dict[str, dict[str, object]] = field(default_factory=dict)
    caption: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "date": {
                    key: value.isoformat()
                    for key, value in self.date.items()
                },
                "gps": {
                    key: {
                        "latitude": value.latitude,
                        "longitude": value.longitude,
                    }
                    for key, value in self.gps.items()
                },
                "location": self.location,
                "caption": self.caption,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, value: str | None) -> "MetadataCandidates":
        if not value:
            return cls()
        data = json.loads(value)
        if not isinstance(data, Mapping):
            raise ValueError("Metadata candidates must be a JSON object.")
        return cls(
            date={
                str(key): datetime.fromisoformat(str(candidate))
                for key, candidate in dict(data.get("date") or {}).items()
            },
            gps={
                str(key): GpsCandidate(
                    latitude=float(candidate["latitude"]),
                    longitude=float(candidate["longitude"]),
                )
                for key, candidate in dict(data.get("gps") or {}).items()
                if isinstance(candidate, Mapping)
            },
            location={
                str(key): dict(candidate)
                for key, candidate in dict(data.get("location") or {}).items()
                if isinstance(candidate, Mapping)
            },
            caption={
                str(key): str(candidate)
                for key, candidate in dict(data.get("caption") or {}).items()
                if str(candidate).strip()
            },
        )

    @property
    def is_empty(self) -> bool:
        return not (self.date or self.gps or self.location or self.caption)
