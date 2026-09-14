from __future__ import annotations

from photoalbum.models import Location

from .cache import GeocodingCache
from .reverse_geocoder import ReverseGeocoder


class LocationResolver:
    def __init__(
        self,
        cache: GeocodingCache,
        geocoder: ReverseGeocoder,
    ) -> None:
        self._cache = cache
        self._geocoder = geocoder

    def resolve(
        self,
        latitude: float,
        longitude: float,
        *,
        language: str | None = None,
        force_refresh: bool = False,
    ) -> Location | None:
        if not force_refresh:
            cached = self._cache.find_nearby(
                latitude,
                longitude,
            )

            if cached is not None:
                return cached

        location = self._geocoder.reverse(
            latitude,
            longitude,
            language=language,
        )

        if location is not None:
            if force_refresh:
                self._cache.replace_nearby(location)
            else:
                self._cache.save(location)

        return location