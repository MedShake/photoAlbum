from __future__ import annotations

from photoalbum.database import ProjectDatabase
from photoalbum.models import Location

from .distance import distance_in_meters


class GeocodingCache:
    def __init__(
        self,
        database: ProjectDatabase,
        reuse_radius_meters: float = 5.0,
    ) -> None:
        if reuse_radius_meters < 0:
            raise ValueError(
                "Geocoding cache reuse radius cannot be negative."
            )

        self._database = database
        self._reuse_radius_meters = reuse_radius_meters

    def find_nearby(
        self,
        latitude: float,
        longitude: float,
    ) -> Location | None:
        rows = self._database.connection.execute(
            """
            SELECT
                latitude,
                longitude,
                place_name,
                city,
                address
            FROM geocoding_cache
            """
        ).fetchall()

        nearest_location: Location | None = None
        nearest_distance: float | None = None

        for row in rows:
            distance = distance_in_meters(
                latitude,
                longitude,
                row["latitude"],
                row["longitude"],
            )

            if distance > self._reuse_radius_meters:
                continue

            if (
                nearest_distance is None
                or distance < nearest_distance
            ):
                nearest_distance = distance
                nearest_location = Location(
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    place_name=row["place_name"],
                    city=row["city"],
                    address=row["address"],
                )

        return nearest_location

    def save(self, location: Location) -> None:
        self._database.connection.execute(
            """
            INSERT INTO geocoding_cache (
                latitude,
                longitude,
                place_name,
                city,
                address
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                location.latitude,
                location.longitude,
                location.place_name,
                location.city,
                location.address,
            ),
        )

        self._database.connection.commit()

    def replace_nearby(
        self,
        location: Location,
    ) -> None:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                latitude,
                longitude
            FROM geocoding_cache
            """
        ).fetchall()

        ids_to_delete: list[int] = []

        for row in rows:
            distance = distance_in_meters(
                location.latitude,
                location.longitude,
                row["latitude"],
                row["longitude"],
            )

            if distance <= self._reuse_radius_meters:
                ids_to_delete.append(row["id"])

        for cache_id in ids_to_delete:
            self._database.connection.execute(
                """
                DELETE FROM geocoding_cache
                WHERE id = ?
                """,
                (cache_id,),
            )

        self._database.connection.execute(
            """
            INSERT INTO geocoding_cache (
                latitude,
                longitude,
                place_name,
                city,
                address
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                location.latitude,
                location.longitude,
                location.place_name,
                location.city,
                location.address,
            ),
        )

        self._database.connection.commit()