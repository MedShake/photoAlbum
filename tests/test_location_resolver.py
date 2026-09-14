from pathlib import Path

from photoalbum.database import ProjectDatabase
from photoalbum.geocoding import (
    GeocodingCache,
    LocationResolver,
)
from photoalbum.models import Location


class FakeGeocoder:
    def __init__(
        self,
        result: Location | None,
    ) -> None:
        self.result = result
        self.calls = 0

    def reverse(
        self,
        latitude: float,
        longitude: float,
        language: str | None = None,
    ) -> Location | None:
        self.calls += 1
        return self.result


def create_resolver(
    tmp_path: Path,
    geocoder: FakeGeocoder,
) -> tuple[
    ProjectDatabase,
    GeocodingCache,
    LocationResolver,
]:
    database = ProjectDatabase(
        tmp_path / "project.photoalbum"
    )
    database.initialize()

    cache = GeocodingCache(database)

    resolver = LocationResolver(
        cache,
        geocoder,
    )

    return database, cache, resolver


def test_cached_location_avoids_geocoder(
    tmp_path: Path,
):
    cached_location = Location(
        latitude=46.670000,
        longitude=-1.570000,
        city="Cached City",
    )

    geocoder = FakeGeocoder(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Network City",
        )
    )

    database, cache, resolver = create_resolver(
        tmp_path,
        geocoder,
    )

    cache.save(cached_location)

    result = resolver.resolve(
        46.670000,
        -1.570000,
    )

    assert result is not None
    assert result.city == "Cached City"
    assert geocoder.calls == 0

    database.close()


def test_missing_cache_uses_geocoder(
    tmp_path: Path,
):
    network_location = Location(
        latitude=46.670000,
        longitude=-1.570000,
        city="Network City",
    )

    geocoder = FakeGeocoder(network_location)

    database, cache, resolver = create_resolver(
        tmp_path,
        geocoder,
    )

    result = resolver.resolve(
        46.670000,
        -1.570000,
    )

    assert result == network_location
    assert geocoder.calls == 1

    database.close()


def test_geocoded_result_is_saved_in_cache(
    tmp_path: Path,
):
    network_location = Location(
        latitude=46.670000,
        longitude=-1.570000,
        city="Network City",
    )

    geocoder = FakeGeocoder(network_location)

    database, cache, resolver = create_resolver(
        tmp_path,
        geocoder,
    )

    resolver.resolve(
        46.670000,
        -1.570000,
    )

    cached = cache.find_nearby(
        46.670000,
        -1.570000,
    )

    assert cached is not None
    assert cached.city == "Network City"

    database.close()


def test_force_refresh_bypasses_cache(
    tmp_path: Path,
):
    geocoder = FakeGeocoder(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Fresh City",
        )
    )

    database, cache, resolver = create_resolver(
        tmp_path,
        geocoder,
    )

    cache.save(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Old City",
        )
    )

    result = resolver.resolve(
        46.670000,
        -1.570000,
        force_refresh=True,
    )

    assert result is not None
    assert result.city == "Fresh City"
    assert geocoder.calls == 1

    database.close()


def test_none_result_is_not_cached(
    tmp_path: Path,
):
    geocoder = FakeGeocoder(None)

    database, cache, resolver = create_resolver(
        tmp_path,
        geocoder,
    )

    result = resolver.resolve(
        46.670000,
        -1.570000,
    )

    assert result is None

    cached = cache.find_nearby(
        46.670000,
        -1.570000,
    )

    assert cached is None

    database.close()


def test_language_is_forwarded_to_geocoder(
    tmp_path: Path,
):
    received_language = None

    class LanguageGeocoder:
        def reverse(
            self,
            latitude: float,
            longitude: float,
            language: str | None = None,
        ) -> Location | None:
            nonlocal received_language
            received_language = language

            return Location(
                latitude=latitude,
                longitude=longitude,
                city="Example City",
            )

    database = ProjectDatabase(
        tmp_path / "project.photoalbum"
    )
    database.initialize()

    cache = GeocodingCache(database)

    resolver = LocationResolver(
        cache,
        LanguageGeocoder(),
    )

    resolver.resolve(
        46.670000,
        -1.570000,
        language="fr",
    )

    assert received_language == "fr"

    database.close()

def test_force_refresh_replaces_cached_location(
    tmp_path: Path,
):
    geocoder = FakeGeocoder(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Fresh City",
        )
    )

    database, cache, resolver = create_resolver(
        tmp_path,
        geocoder,
    )

    cache.save(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Old City",
        )
    )

    resolver.resolve(
        46.670000,
        -1.570000,
        force_refresh=True,
    )

    cached = cache.find_nearby(
        46.670000,
        -1.570000,
    )

    assert cached is not None
    assert cached.city == "Fresh City"

    database.close()


def test_failed_force_refresh_keeps_old_cache(
    tmp_path: Path,
):
    geocoder = FakeGeocoder(None)

    database, cache, resolver = create_resolver(
        tmp_path,
        geocoder,
    )

    cache.save(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Old City",
        )
    )

    result = resolver.resolve(
        46.670000,
        -1.570000,
        force_refresh=True,
    )

    assert result is None

    cached = cache.find_nearby(
        46.670000,
        -1.570000,
    )

    assert cached is not None
    assert cached.city == "Old City"

    database.close()