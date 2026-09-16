from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from photoalbum.models import Location

from .cache import GeocodingCache
from .reverse_geocoder import ReverseGeocoder


class LocationResolutionSource(str, Enum):
    CACHE = "cache"
    REVERSE = "reverse"


@dataclass(frozen=True)
class LocationResolution:
    location: Location | None
    source: LocationResolutionSource


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
        return self.resolve_with_source(
            latitude,
            longitude,
            language=language,
            force_refresh=force_refresh,
        ).location

    def resolve_with_source(
        self,
        latitude: float,
        longitude: float,
        *,
        language: str | None = None,
        force_refresh: bool = False,
    ) -> LocationResolution:
        if not force_refresh:
            cached = self._cache.find_nearby(
                latitude,
                longitude,
            )

            if cached is not None:
                return LocationResolution(
                    location=cached,
                    source=LocationResolutionSource.CACHE,
                )

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

        return LocationResolution(
            location=location,
            source=LocationResolutionSource.REVERSE,
        )
