from __future__ import annotations

from photoalbum.database import ProjectDatabase

from .cache import GeocodingCache
from .location_resolver import LocationResolver
from .nominatim_geocoder import NominatimGeocoder


def create_nominatim_location_resolver(
    database: ProjectDatabase,
    *,
    user_agent: str,
    endpoint: str = NominatimGeocoder.DEFAULT_ENDPOINT,
    reuse_radius_meters: float = 5.0,
    timeout_seconds: float = 10.0,
) -> LocationResolver:
    cache = GeocodingCache(
        database,
        reuse_radius_meters=reuse_radius_meters,
    )

    geocoder = NominatimGeocoder(
        user_agent=user_agent,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
    )

    return LocationResolver(
        cache,
        geocoder,
    )

