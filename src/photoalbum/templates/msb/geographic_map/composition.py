from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from photoalbum.models import Photo

from .geography import (
    GeographicBounds,
    Point,
    map_bounds_for_points,
    longitude_near_reference,
)


@dataclass(frozen=True)
class GeographicMapMarker:
    longitude: float
    latitude: float
    x: float
    y: float
    month: int | None


@dataclass(frozen=True)
class GeographicMap:
    bounds: GeographicBounds
    markers: tuple[GeographicMapMarker, ...]


def eligible_photos(
    photos: list[Photo] | tuple[Photo, ...],
    year: int | None,
) -> list[Photo]:
    result = {}

    for photo in photos:
        if year is not None:
            capture = photo.capture_datetime

            if (
                capture is None
                or capture.year != year
            ):
                continue

        if (
            photo.latitude is None
            or photo.longitude is None
        ):
            continue

        try:
            longitude, latitude = float(photo.longitude), float(photo.latitude)
        except (ValueError, TypeError):
            continue
        if not (isfinite(longitude) and isfinite(latitude)
                and -180 <= longitude <= 180 and -90 <= latitude <= 90):
            continue
        result.setdefault(photo.identity, photo)

    return [result[key] for key in sorted(result)]


def _normalized_position(
    longitude: float,
    latitude: float,
    bounds: GeographicBounds,
) -> tuple[float, float]:
    """Legacy normalized lon/lat fields, not the painter's map projection."""
    longitude = longitude_near_reference(
        longitude, (bounds.minimum_longitude + bounds.maximum_longitude) / 2
    )
    longitude_span = bounds.longitude_span
    latitude_span = bounds.latitude_span

    x = (
        0.5
        if longitude_span == 0
        else (
            longitude - bounds.minimum_longitude
        ) / longitude_span
    )

    y = (
        0.5
        if latitude_span == 0
        else (
            bounds.maximum_latitude - latitude
        ) / latitude_span
    )

    return x, y


def compose_geographic_map(
    photos: list[Photo] | tuple[Photo, ...],
    *,
    year: int | None = None,
) -> GeographicMap:
    eligible = eligible_photos(
        photos,
        year,
    )

    points: list[Point] = [
        (
            float(photo.longitude),
            float(photo.latitude),
        )
        for photo in eligible
    ]

    bounds = map_bounds_for_points(points)

    markers = []

    for photo in eligible:
        longitude = float(photo.longitude)
        latitude = float(photo.latitude)

        x, y = _normalized_position(
            longitude,
            latitude,
            bounds,
        )

        capture = photo.capture_datetime

        markers.append(
            GeographicMapMarker(
                longitude=longitude,
                latitude=latitude,
                x=x,
                y=y,
                month=(
                    capture.month
                    if capture is not None
                    else None
                ),
            )
        )

    return GeographicMap(
        bounds=bounds,
        markers=tuple(markers),
    )
