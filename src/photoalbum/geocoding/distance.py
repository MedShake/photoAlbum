from __future__ import annotations

from math import asin, cos, radians, sin, sqrt


EARTH_RADIUS_METERS = 6_371_000.0


def distance_in_meters(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    """
    Calculate the great-circle distance between two GPS coordinates.

    The returned distance is expressed in meters.
    """

    lat1 = radians(latitude1)
    lon1 = radians(longitude1)
    lat2 = radians(latitude2)
    lon2 = radians(longitude2)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(delta_lon / 2) ** 2
    )

    central_angle = 2 * asin(sqrt(haversine))

    return EARTH_RADIUS_METERS * central_angle

