from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .location_candidate import (
    LocationCandidate,
    LocationCandidatePriority,
)


class LocationCandidateExtractor:
    PLACE_KEYS = {
        "tourism",
        "amenity",
        "historic",
        "leisure",
        "shop",
        "building",
        "office",
        "attraction",
    }

    ROAD_KEYS = {
        "road",
        "pedestrian",
        "square",
        "residential",
        "footway",
        "path",
    }

    LOCAL_CONTEXT_KEYS = {
        "neighbourhood",
        "quarter",
        "suburb",
        "borough",
        "city_district",
    }

    LOCALITY_KEYS = {
        "city",
        "town",
        "village",
        "municipality",
        "hamlet",
        "isolated_dwelling",
    }

    ADMINISTRATIVE_KEYS = {
        "county",
        "state_district",
        "state",
        "region",
    }

    POSTAL_KEYS = {
        "house_number",
        "postcode",
    }

    COUNTRY_KEYS = {
        "country",
    }

    def extract(
        self,
        raw_data: Mapping[str, Any] | None,
    ) -> list[LocationCandidate]:
        if not raw_data:
            return []

        address_data = raw_data.get("address")

        if not isinstance(address_data, Mapping):
            return []

        candidates: list[LocationCandidate] = []

        for key, value in address_data.items():
            if not isinstance(key, str):
                continue

            if not isinstance(value, str):
                continue

            value = value.strip()

            if not value:
                continue

            candidates.append(
                LocationCandidate(
                    key=key,
                    value=value,
                    priority=self._priority_for(key),
                )
            )

        return candidates

    def _priority_for(
        self,
        key: str,
    ) -> LocationCandidatePriority:
        if key in self.PLACE_KEYS:
            return LocationCandidatePriority.PLACE

        if key in self.ROAD_KEYS:
            return LocationCandidatePriority.ROAD

        if key in self.LOCAL_CONTEXT_KEYS:
            return LocationCandidatePriority.LOCAL_CONTEXT

        if key in self.LOCALITY_KEYS:
            return LocationCandidatePriority.LOCALITY

        if key in self.ADMINISTRATIVE_KEYS:
            return LocationCandidatePriority.ADMINISTRATIVE

        if key in self.POSTAL_KEYS:
            return LocationCandidatePriority.POSTAL

        if key in self.COUNTRY_KEYS:
            return LocationCandidatePriority.COUNTRY

        return LocationCandidatePriority.OTHER
