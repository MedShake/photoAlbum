from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from photoalbum.models import Location


class NominatimParser:
    """
    Convert a Nominatim reverse-geocoding response into a Location.
    """

    CITY_KEYS = (
        "city",
        "town",
        "village",
        "municipality",
        "hamlet",
    )

    PLACE_KEYS = (
        "tourism",
        "amenity",
        "building",
        "shop",
        "leisure",
        "historic",
        "office",
    )

    def parse(
        self,
        data: Mapping[str, Any],
        latitude: float,
        longitude: float,
    ) -> Location | None:
        if not data:
            return None

        address_data = data.get("address")

        if not isinstance(address_data, Mapping):
            address_data = {}

        city = self._first_string(
            address_data,
            self.CITY_KEYS,
        )

        place_name = self._first_string(
            address_data,
            self.PLACE_KEYS,
        )

        display_name = data.get("display_name")

        if not isinstance(display_name, str):
            display_name = None

        return Location(
            latitude=latitude,
            longitude=longitude,
            place_name=place_name,
            city=city,
            address=display_name,
            raw_data=dict(data),
        )

    @staticmethod
    def _first_string(
        data: Mapping[str, Any],
        keys: tuple[str, ...],
    ) -> str | None:
        for key in keys:
            value = data.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

        return None

