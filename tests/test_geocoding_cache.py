from pathlib import Path

import pytest

from photoalbum.database import ProjectDatabase
from photoalbum.geocoding import GeocodingCache
from photoalbum.models import Location


def create_cache(
    tmp_path: Path,
    reuse_radius_meters: float = 5.0,
) -> tuple[ProjectDatabase, GeocodingCache]:
    database = ProjectDatabase(
        tmp_path / "project.photoalbum"
    )
    database.initialize()

    cache = GeocodingCache(
        database,
        reuse_radius_meters=reuse_radius_meters,
    )

    return database, cache


def test_cache_returns_exact_location(tmp_path: Path):
    database, cache = create_cache(tmp_path)

    location = Location(
        latitude=46.670000,
        longitude=-1.570000,
        place_name="Example Place",
        city="Example City",
        address="1 Example Street",
    )

    cache.save(location)

    result = cache.find_nearby(
        46.670000,
        -1.570000,
    )

    assert result == location

    database.close()


def test_cache_reuses_location_within_five_meters(
    tmp_path: Path,
):
    database, cache = create_cache(tmp_path)

    cache.save(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Example City",
        )
    )

    result = cache.find_nearby(
        46.670036,
        -1.570000,
    )

    assert result is not None
    assert result.city == "Example City"

    database.close()


def test_cache_ignores_location_beyond_radius(
    tmp_path: Path,
):
    database, cache = create_cache(tmp_path)

    cache.save(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Example City",
        )
    )

    result = cache.find_nearby(
        46.670090,
        -1.570000,
    )

    assert result is None

    database.close()


def test_cache_returns_nearest_location(
    tmp_path: Path,
):
    database, cache = create_cache(
        tmp_path,
        reuse_radius_meters=20.0,
    )

    cache.save(
        Location(
            latitude=46.670030,
            longitude=-1.570000,
            city="Nearest",
        )
    )

    cache.save(
        Location(
            latitude=46.670100,
            longitude=-1.570000,
            city="Farther",
        )
    )

    result = cache.find_nearby(
        46.670000,
        -1.570000,
    )

    assert result is not None
    assert result.city == "Nearest"

    database.close()


def test_cache_radius_can_be_configured(tmp_path: Path):
    database, cache = create_cache(
        tmp_path,
        reuse_radius_meters=2.0,
    )

    cache.save(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Example City",
        )
    )

    result = cache.find_nearby(
        46.670036,
        -1.570000,
    )

    assert result is None

    database.close()


def test_negative_cache_radius_is_rejected(
    tmp_path: Path,
):
    database = ProjectDatabase(
        tmp_path / "project.photoalbum"
    )
    database.initialize()

    with pytest.raises(ValueError):
        GeocodingCache(
            database,
            reuse_radius_meters=-1.0,
        )

    database.close()

def test_replace_nearby_removes_old_location(
    tmp_path: Path,
):
    database, cache = create_cache(tmp_path)

    cache.save(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Old City",
        )
    )

    cache.replace_nearby(
        Location(
            latitude=46.670001,
            longitude=-1.570000,
            city="Fresh City",
        )
    )

    result = cache.find_nearby(
        46.670000,
        -1.570000,
    )

    assert result is not None
    assert result.city == "Fresh City"

    database.close()


def test_replace_nearby_keeps_distant_locations(
    tmp_path: Path,
):
    database, cache = create_cache(tmp_path)

    distant = Location(
        latitude=46.680000,
        longitude=-1.570000,
        city="Distant City",
    )

    cache.save(distant)

    cache.replace_nearby(
        Location(
            latitude=46.670000,
            longitude=-1.570000,
            city="Fresh City",
        )
    )

    result = cache.find_nearby(
        distant.latitude,
        distant.longitude,
    )

    assert result is not None
    assert result.city == "Distant City"

    database.close()

def test_cache_preserves_raw_data(tmp_path: Path):
    database, cache = create_cache(tmp_path)

    raw_data = {
        "place_id": 123456,
        "display_name": "Example Place, Nantes, France",
        "address": {
            "road": "Rue Example",
            "city": "Nantes",
            "state": "Pays de la Loire",
            "country": "France",
        },
    }

    location = Location(
        latitude=47.2184,
        longitude=-1.5536,
        place_name="Example Place",
        city="Nantes",
        address="Example Place, Nantes, France",
        raw_data=raw_data,
    )

    cache.save(location)

    loaded = cache.find_nearby(
        location.latitude,
        location.longitude,
    )

    assert loaded is not None
    assert loaded.raw_data == raw_data

    database.close()
