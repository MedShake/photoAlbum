from __future__ import annotations

from datetime import datetime

from photoalbum.models import Photo
from photoalbum.templates.msb.geographic_map.composition import (
    compose_geographic_map,
)
from photoalbum.templates.msb.geographic_map.geography import (
    containing_component,
    load_countries,
    map_bounds_for_points,
)


def _photo(
    *,
    latitude: float,
    longitude: float,
    year: int = 2026,
) -> Photo:
    filename = f"{latitude}-{longitude}.jpg"
    photo = Photo(
        path=f"/tmp/{filename}",
        filename=filename,
    )
    photo.latitude = latitude
    photo.longitude = longitude
    photo.capture_datetime = datetime(
        year,
        1,
        1,
        12,
        0,
    )
    return photo


def test_natural_earth_data_is_available() -> None:
    countries = load_countries()

    assert len(countries) >= 200

    names = {country.name for country in countries}

    assert "France" in names
    assert "Spain" in names
    assert "Germany" in names
    assert "United States of America" in names


def test_nantes_is_in_french_component() -> None:
    match = containing_component(
        -1.5536,
        47.2184,
    )

    assert match is not None

    country, _ring = match

    assert country.name == "France"


def test_single_point_uses_country_component_extent() -> None:
    bounds = map_bounds_for_points(
        [(-1.5536, 47.2184)]
    )

    # Nantes alone must still show metropolitan France rather than
    # zooming to the city.
    assert bounds.minimum_longitude < -4.0
    assert bounds.maximum_longitude > 7.0
    assert bounds.minimum_latitude < 43.0
    assert bounds.maximum_latitude > 50.0

    # Overseas French components must not force a world-scale map.
    assert bounds.longitude_span < 20.0
    assert bounds.latitude_span < 20.0


def test_france_and_spain_expand_extent() -> None:
    bounds = map_bounds_for_points(
        [
            (-1.5536, 47.2184),
            (-3.7038, 40.4168),
        ]
    )

    assert bounds.minimum_longitude < -9.0
    assert bounds.maximum_longitude > 7.0
    assert bounds.minimum_latitude < 36.0
    assert bounds.maximum_latitude > 50.0


def test_composition_filters_by_year() -> None:
    photos = [
        _photo(
            latitude=47.2184,
            longitude=-1.5536,
            year=2025,
        ),
        _photo(
            latitude=48.8566,
            longitude=2.3522,
            year=2026,
        ),
    ]

    result = compose_geographic_map(
        photos,
        year=2026,
    )

    assert len(result.markers) == 1
    assert result.markers[0].longitude == 2.3522
    assert result.markers[0].latitude == 48.8566


def test_markers_are_projected_inside_map() -> None:
    photos = [
        _photo(
            latitude=47.2184,
            longitude=-1.5536,
        ),
        _photo(
            latitude=43.2965,
            longitude=5.3698,
        ),
    ]

    result = compose_geographic_map(photos)

    assert len(result.markers) == 2

    for marker in result.markers:
        assert 0.0 <= marker.x <= 1.0
        assert 0.0 <= marker.y <= 1.0
