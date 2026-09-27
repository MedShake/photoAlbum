from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from math import ceil, floor


Point = tuple[float, float]
Ring = tuple[Point, ...]


@dataclass(frozen=True)
class Country:
    name: str
    iso_a2: str
    iso_a3: str
    rings: tuple[Ring, ...]


@dataclass(frozen=True)
class GeographicBounds:
    minimum_longitude: float
    minimum_latitude: float
    maximum_longitude: float
    maximum_latitude: float

    @property
    def longitude_span(self) -> float:
        return self.maximum_longitude - self.minimum_longitude

    @property
    def latitude_span(self) -> float:
        return self.maximum_latitude - self.minimum_latitude


def _data_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "assets"
        / "geographic_map"
        / "countries.json"
    )


@lru_cache(maxsize=1)
def load_countries() -> tuple[Country, ...]:
    payload = json.loads(
        _data_path().read_text(encoding="utf-8")
    )

    countries = []

    for raw_country in payload["countries"]:
        rings = tuple(
            tuple(
                (float(longitude), float(latitude))
                for longitude, latitude in raw_ring
            )
            for raw_ring in raw_country["rings"]
        )

        countries.append(
            Country(
                name=str(raw_country["name"]),
                iso_a2=str(raw_country["iso_a2"]),
                iso_a3=str(raw_country["iso_a3"]),
                rings=rings,
            )
        )

    return tuple(countries)


def normalize_longitude(
    longitude: float,
) -> float:
    """Normalize longitude to [-180, 180)."""
    return (
        (float(longitude) + 180.0)
        % 360.0
    ) - 180.0


def unwrap_longitude(
    longitude: float,
    minimum_longitude: float,
) -> float:
    """
    Represent longitude in the continuous 360-degree interval
    starting at minimum_longitude.

    Example: with a start at 178°, -179° becomes 181°.
    """
    return minimum_longitude + (float(longitude) - minimum_longitude) % 360.0


def longitude_near_reference(
    longitude: float,
    reference_longitude: float,
) -> float:
    """
    Return the equivalent longitude nearest a reference
    longitude.

    This is intended for rendering into a selected world copy:
    values just outside a viewport remain just outside it,
    while values across the antimeridian move by 360 degrees
    when that makes them geographically adjacent.
    """
    return reference_longitude + 180.0 - (reference_longitude - longitude + 180.0) % 360.0


def minimal_longitude_interval(
    longitudes,
) -> tuple[float, float]:
    """
    Return the smallest continuous longitude arc containing
    all values.

    The maximum is intentionally allowed to exceed +180°.
    """
    extents = [GeographicBounds(value, 0.0, value, 0.0) for value in longitudes]
    return _cover_longitude_intervals(extents) if extents else (-180.0, 180.0)


def ring_bounds(ring: Ring) -> GeographicBounds:
    longitudes = [point[0] for point in ring]
    latitudes = [point[1] for point in ring]

    return GeographicBounds(
        minimum_longitude=min(longitudes),
        minimum_latitude=min(latitudes),
        maximum_longitude=max(longitudes),
        maximum_latitude=max(latitudes),
    )


def continuous_ring(ring: Ring) -> Ring:
    """Unwrap connected edges once, independently of the viewport.

    Explicit pole-to-pole-seam edges in Natural Earth's polar cap are
    intentional planar boundaries, not shortest-arc geographic edges.
    """
    if not ring:
        return ()
    result = [ring[0]]
    for longitude, latitude in ring[1:]:
        previous, previous_latitude = result[-1]
        if abs(latitude) == 90 and latitude == previous_latitude:
            result.append((longitude, latitude))
        else:
            result.append((longitude_near_reference(longitude, previous), latitude))
    return tuple(result)


@lru_cache(maxsize=1)
def country_components():
    """Immutable geometry/index shared by composition and every render."""
    return tuple(
        (country, ring, ring_bounds(ring))
        for country in load_countries()
        for source in country.rings
        if (ring := continuous_ring(source))
    )


def world_offsets(extent: GeographicBounds, bounds: GeographicBounds):
    """Copies of an entire component overlapping a continuous viewport."""
    if (extent.maximum_latitude < bounds.minimum_latitude
            or extent.minimum_latitude > bounds.maximum_latitude):
        return range(0)
    first = ceil((bounds.minimum_longitude - extent.maximum_longitude) / 360)
    last = floor((bounds.maximum_longitude - extent.minimum_longitude) / 360)
    return (360.0 * index for index in range(first, last + 1))


def point_in_ring(
    longitude: float,
    latitude: float,
    ring: Ring,
) -> bool:
    """Test a point and ring already expressed in the same continuous world.

    Natural Earth 1:50m is used only to choose the visual map extent.
    Boundary precision at local scale is deliberately not required.
    """
    if len(ring) < 3:
        return False

    bounds = ring_bounds(ring)

    if not (
        bounds.minimum_longitude <= longitude <= bounds.maximum_longitude
        and bounds.minimum_latitude <= latitude <= bounds.maximum_latitude
    ):
        return False

    inside = False
    previous_longitude, previous_latitude = ring[-1]

    for current_longitude, current_latitude in ring:
        crosses = (
            (current_latitude > latitude)
            != (previous_latitude > latitude)
        )

        if crosses:
            intersection_longitude = (
                (previous_longitude - current_longitude)
                * (latitude - current_latitude)
                / (previous_latitude - current_latitude)
                + current_longitude
            )

            if longitude < intersection_longitude:
                inside = not inside

        previous_longitude = current_longitude
        previous_latitude = current_latitude

    return inside


def containing_component(
    longitude: float,
    latitude: float,
    countries: tuple[Country, ...] | None = None,
) -> tuple[Country, Ring] | None:
    components = (
        country_components() if countries is None else
        ((country, continuous_ring(ring), ring_bounds(continuous_ring(ring)))
         for country in countries for ring in country.rings)
    )
    for country, ring, extent in components:
        local_longitude = longitude_near_reference(
            longitude, (extent.minimum_longitude + extent.maximum_longitude) / 2
        )
        if not (extent.minimum_longitude <= local_longitude <= extent.maximum_longitude
                and extent.minimum_latitude <= latitude <= extent.maximum_latitude):
            continue
        if point_in_ring(local_longitude, latitude, ring):
            return country, ring
    return None


def bounds_for_rings(
    rings: list[Ring] | tuple[Ring, ...],
) -> GeographicBounds:
    if not rings:
        raise ValueError("At least one ring is required")

    bounds = [ring_bounds(continuous_ring(ring)) for ring in rings]
    minimum, maximum = _cover_longitude_intervals(bounds)
    return GeographicBounds(
        minimum, min(item.minimum_latitude for item in bounds),
        maximum, max(item.maximum_latitude for item in bounds),
    )


def _cover_longitude_intervals(extents):
    """Cut in the largest *unoccupied* gap, never through a component.

    A minimum arc over vertices alone can cut an edge or the interior of a
    polygon. Merge occupied circular intervals before choosing the cut.
    """
    intervals = []
    for extent in extents:
        if extent.longitude_span >= 360:
            return -180.0, 180.0
        start = extent.minimum_longitude % 360
        end = start + extent.longitude_span
        if end > 360:
            intervals.extend(((start, 360.0), (0.0, end - 360)))
        else:
            intervals.append((start, end))
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    gaps = [
        ((merged[(i + 1) % len(merged)][0] + (360 if i == len(merged) - 1 else 0)) - end,
         merged[(i + 1) % len(merged)][0])
        for i, (_start, end) in enumerate(merged)
    ]
    gap, start = max(gaps)
    start = normalize_longitude(start)
    return start, start + 360 - gap


def padded_bounds(
    bounds: GeographicBounds,
    *,
    fraction: float = 0.08,
) -> GeographicBounds:
    longitude_padding = max(
        bounds.longitude_span * fraction,
        0.5,
    )
    latitude_padding = max(
        bounds.latitude_span * fraction,
        0.5,
    )

    longitude_padding = min(longitude_padding, max(0.0, (360 - bounds.longitude_span) / 2))

    return GeographicBounds(
        minimum_longitude=(
            bounds.minimum_longitude
            - longitude_padding
        ),
        minimum_latitude=max(
            -90.0,
            bounds.minimum_latitude - latitude_padding,
        ),
        maximum_longitude=(
            bounds.maximum_longitude
            + longitude_padding
        ),
        maximum_latitude=min(
            90.0,
            bounds.maximum_latitude + latitude_padding,
        ),
    )


def map_bounds_for_points(
    points: list[Point] | tuple[Point, ...],
) -> GeographicBounds:
    """Choose the map extent, never tighter than a country component.

    Each photo point contributes the Natural Earth polygon component
    containing it. This intentionally avoids pulling distant overseas
    components into a local map.

    Points not covered by Natural Earth still participate directly in
    the resulting extent.
    """
    if not points:
        return GeographicBounds(
            minimum_longitude=-180.0,
            minimum_latitude=-90.0,
            maximum_longitude=180.0,
            maximum_latitude=90.0,
        )

    selected_rings: list[Ring] = []

    seen: set[tuple[str, Ring]] = set()

    for longitude, latitude in dict.fromkeys(points):
        match = containing_component(
            longitude,
            latitude,
        )

        if match is None:
            continue

        country, ring = match
        key = (country.name, ring)

        if key not in seen:
            seen.add(key)
            selected_rings.append(ring)

    extents = [ring_bounds(ring) for ring in selected_rings]
    # Keep all markers explicitly, including boundary/coastline points.
    extents.extend(GeographicBounds(lon, lat, lon, lat) for lon, lat in points)
    minimum, maximum = _cover_longitude_intervals(extents)
    return padded_bounds(GeographicBounds(
        minimum, min(item.minimum_latitude for item in extents),
        maximum, max(item.maximum_latitude for item in extents),
    ))
