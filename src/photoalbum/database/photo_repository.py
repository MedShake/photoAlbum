from __future__ import annotations

import json

from datetime import datetime
from pathlib import Path

from photoalbum.models import (
    DateSource,
    LocationComponent,
    LocationSource,
    Photo,
)

from .database import ProjectDatabase


class PhotoRepository:
    def __init__(self, database: ProjectDatabase) -> None:
        self._database = database

    def save(self, photo: Photo) -> None:
        capture_datetime = (
            photo.capture_datetime.isoformat()
            if photo.capture_datetime is not None
            else None
        )

        original_capture_datetime = (
            photo.original_capture_datetime.isoformat()
            if photo.original_capture_datetime is not None
            else capture_datetime
        )

        self._database.connection.execute(
            """
            INSERT INTO photos (
                path,
                filename,
                file_size,
                modified_time_ns,
                content_hash,
                width,
                height,
                orientation,
                capture_datetime,
                date_source,
                latitude,
                longitude,
                original_orientation,
                original_capture_datetime,
                original_date_source,
                original_latitude,
                original_longitude,
                place_name,
                city,
                address,
                raw_location_data,
                location_source,
                selected_location_components,
                location_text,
                location_selection_edited,
                caption,
                is_missing
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            ON CONFLICT(path) DO UPDATE SET
                filename = excluded.filename,
                file_size = excluded.file_size,
                modified_time_ns = excluded.modified_time_ns,
                content_hash = excluded.content_hash,
                width = excluded.width,
                height = excluded.height,
                orientation = excluded.orientation,
                capture_datetime = excluded.capture_datetime,
                date_source = excluded.date_source,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                original_orientation = excluded.original_orientation,
                original_capture_datetime = excluded.original_capture_datetime,
                original_date_source = excluded.original_date_source,
                original_latitude = excluded.original_latitude,
                original_longitude = excluded.original_longitude,
                place_name = excluded.place_name,
                city = excluded.city,
                address = excluded.address,
                raw_location_data = excluded.raw_location_data,
                location_source = excluded.location_source,
                selected_location_components =
                    excluded.selected_location_components,
                location_text = excluded.location_text,
                location_selection_edited =
                    excluded.location_selection_edited,
                caption = excluded.caption,
                is_missing = 0
            """,
            (
                str(photo.path),
                photo.filename,
                photo.file_size,
                photo.modified_time_ns,
                photo.content_hash,
                photo.width,
                photo.height,
                photo.orientation,
                capture_datetime,
                photo.date_source.value,
                photo.latitude,
                photo.longitude,
                (
                    photo.original_orientation
                    if photo.original_orientation is not None
                    else photo.orientation
                ),
                original_capture_datetime,
                (
                    photo.original_date_source.value
                    if photo.original_date_source != DateSource.UNKNOWN
                    else photo.date_source.value
                ),
                (
                    photo.original_latitude
                    if photo.original_latitude is not None
                    else photo.latitude
                ),
                (
                    photo.original_longitude
                    if photo.original_longitude is not None
                    else photo.longitude
                ),
                photo.place_name,
                photo.city,
                photo.address,
                (
                    json.dumps(
                        photo.raw_location_data,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    if photo.raw_location_data is not None
                    else None
                ),
                photo.location_source.value,
                (
                    json.dumps(
                        [
                            {
                                "key": component.key,
                                "value": component.value,
                            }
                            for component
                            in photo.selected_location_components
                        ],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    if photo.selected_location_components
                    else None
                ),
                photo.location_text,
                1 if photo.location_selection_edited else 0,
                photo.caption,
                0,
            ),
        )

        self._database.connection.commit()

    def find_by_path(self, path: Path) -> Photo | None:
        row = self._database.connection.execute(
            """
            SELECT *
            FROM photos
            WHERE path = ?
            """,
            (str(path),),
        ).fetchone()

        if row is None:
            return None

        return self._row_to_photo(row)

    def list_all(
        self,
        *,
        include_missing: bool = False,
    ) -> list[Photo]:
        if include_missing:
            rows = self._database.connection.execute(
                """
                SELECT *
                FROM photos
                ORDER BY capture_datetime, filename
                """
            ).fetchall()
        else:
            rows = self._database.connection.execute(
                """
                SELECT *
                FROM photos
                WHERE is_missing = 0
                ORDER BY capture_datetime, filename
                """
            ).fetchall()

        return [
            self._row_to_photo(row)
            for row in rows
        ]

    def is_missing(
        self,
        path: Path,
    ) -> bool:
        row = self._database.connection.execute(
            """
            SELECT is_missing
            FROM photos
            WHERE path = ?
            """,
            (str(path),),
        ).fetchone()

        if row is None:
            return False

        return bool(row["is_missing"])

    def set_missing(
        self,
        path: Path,
        missing: bool,
    ) -> None:
        self._database.connection.execute(
            """
            UPDATE photos
            SET is_missing = ?
            WHERE path = ?
            """,
            (
                1 if missing else 0,
                str(path),
            ),
        )

        self._database.connection.commit()

    def restore_original_capture_datetime(
        self,
        path: Path,
    ) -> None:
        normalized_path = str(
            path.expanduser().resolve()
        )

        cursor = self._database.connection.execute(
            """
            UPDATE photos
            SET
                capture_datetime = original_capture_datetime,
                date_source = original_date_source
            WHERE path = ?
            """,
            (normalized_path,),
        )

        if cursor.rowcount == 0:
            raise KeyError(
                f"Photo not found: {normalized_path}"
            )

        self._database.connection.commit()

    def set_manual_capture_datetime(
        self,
        path: Path,
        capture_datetime: datetime,
    ) -> None:
        cursor = self._database.connection.execute(
            """
            UPDATE photos
            SET capture_datetime = ?,
                date_source = ?
            WHERE path = ?
            """,
            (
                capture_datetime.isoformat(),
                DateSource.MANUAL.value,
                str(path),
            ),
        )

        if cursor.rowcount == 0:
            raise KeyError(
                f"Photo is not registered in the project: {path}"
            )

        self._database.connection.commit()

    def set_manual_gps(
        self,
        path: Path,
        latitude: float,
        longitude: float,
    ) -> None:
        if not -90.0 <= latitude <= 90.0:
            raise ValueError(
                "Latitude must be between -90 and 90."
            )

        if not -180.0 <= longitude <= 180.0:
            raise ValueError(
                "Longitude must be between -180 and 180."
            )

        normalized_path = str(
            path.expanduser().resolve()
        )

        cursor = self._database.connection.execute(
            """
            UPDATE photos
            SET
                latitude = ?,
                longitude = ?,
                place_name = NULL,
                city = NULL,
                address = NULL,
                location_source = ?
            WHERE path = ?
            """,
            (
                latitude,
                longitude,
                LocationSource.MANUAL.value,
                normalized_path,
            ),
        )

        if cursor.rowcount == 0:
            raise KeyError(
                f"Photo not found: {normalized_path}"
            )

        self._database.connection.commit()

    def restore_original_gps(
        self,
        path: Path,
    ) -> None:
        normalized_path = str(
            path.expanduser().resolve()
        )

        cursor = self._database.connection.execute(
            """
            UPDATE photos
            SET
                latitude = original_latitude,
                longitude = original_longitude,
                place_name = NULL,
                city = NULL,
                address = NULL,
                location_source = ?
            WHERE path = ?
            """,
            (
                LocationSource.UNKNOWN.value,
                normalized_path,
            ),
        )

        if cursor.rowcount == 0:
            raise KeyError(
                f"Photo not found: {normalized_path}"
            )

        self._database.connection.commit()

    def set_geocoded_location(
        self,
        path: Path,
        *,
        place_name: str | None,
        city: str | None,
        address: str | None,
        raw_location_data: dict[str, object] | None = None,
    ) -> None:
        normalized_path = str(
            path.expanduser().resolve()
        )

        cursor = self._database.connection.execute(
            """
            UPDATE photos
            SET
                place_name = ?,
                city = ?,
                address = ?,
                raw_location_data = ?,
                location_source = ?
            WHERE path = ?
            """,
            (
                place_name,
                city,
                address,
                (
                    json.dumps(
                        raw_location_data,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    if raw_location_data is not None
                    else None
                ),
                LocationSource.GEOCODING.value,
                normalized_path,
            ),
        )

        if cursor.rowcount == 0:
            raise KeyError(
                f"Photo not found: {normalized_path}"
            )

        self._database.connection.commit()

    def set_caption(
        self,
        path: Path,
        caption: str | None,
    ) -> None:
        normalized_path = str(
            path.expanduser().resolve()
        )

        if caption is not None:
            caption = caption.strip()

        cursor = self._database.connection.execute(
            """
            UPDATE photos
            SET caption = ?
            WHERE path = ?
            """,
            (
                caption or None,
                normalized_path,
            ),
        )

        if cursor.rowcount == 0:
            raise KeyError(
                f"Photo not found: {normalized_path}"
            )

        self._database.connection.commit()

    def set_editorial_location(
        self,
        path: Path,
        *,
        components: tuple[LocationComponent, ...],
        location_text: str | None,
    ) -> None:
        normalized_path = str(
            path.expanduser().resolve()
        )

        serialized_components = (
            json.dumps(
                [
                    {
                        "key": component.key,
                        "value": component.value,
                    }
                    for component in components
                ],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if components
            else None
        )

        cursor = self._database.connection.execute(
            """
            UPDATE photos
            SET
                selected_location_components = ?,
                location_text = ?,
                location_selection_edited = 1
            WHERE path = ?
            """,
            (
                serialized_components,
                location_text,
                normalized_path,
            ),
        )

        if cursor.rowcount == 0:
            raise KeyError(
                f"Photo not found: {normalized_path}"
            )

        self._database.connection.commit()

    def set_manual_location(
        self,
        path: Path,
        *,
        place_name: str | None = None,
        city: str | None = None,
        address: str | None = None,
    ) -> None:
        cursor = self._database.connection.execute(
            """
            UPDATE photos
            SET place_name = ?,
                city = ?,
                address = ?,
                raw_location_data = ?,
                location_source = ?
            WHERE path = ?
            """,
            (
                place_name,
                city,
                address,
                None,
                LocationSource.MANUAL.value,
                str(path),
            ),
        )

        if cursor.rowcount == 0:
            raise KeyError(
                f"Photo is not registered in the project: {path}"
            )

        self._database.connection.commit()

    def update_geocoded_location(
        self,
        photo: Photo,
    ) -> None:
        cursor = self._database.connection.execute(
            """
            UPDATE photos
            SET place_name = ?,
                city = ?,
                address = ?,
                raw_location_data = ?,
                location_source = ?
            WHERE path = ?
            """,
            (
                photo.place_name,
                photo.city,
                photo.address,
                (
                    json.dumps(
                        photo.raw_location_data,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    if photo.raw_location_data is not None
                    else None
                ),
                LocationSource.GEOCODING.value,
                str(photo.path),
            ),
        )

        if cursor.rowcount == 0:
            raise KeyError(
                "Photo is not registered in the project: "
                f"{photo.path}"
            )

        self._database.connection.commit()

    @staticmethod
    def _row_to_photo(row) -> Photo:
        capture_datetime = (
            datetime.fromisoformat(row["capture_datetime"])
            if row["capture_datetime"] is not None
            else None
        )

        original_capture_datetime = (
            datetime.fromisoformat(
                row["original_capture_datetime"]
            )
            if row["original_capture_datetime"] is not None
            else None
        )

        return Photo(
            path=Path(row["path"]),
            filename=row["filename"],
            file_size=row["file_size"],
            modified_time_ns=row["modified_time_ns"],
            content_hash=row["content_hash"],
            width=row["width"],
            height=row["height"],
            orientation=row["orientation"],
            capture_datetime=capture_datetime,
            date_source=DateSource(row["date_source"]),
            latitude=row["latitude"],
            longitude=row["longitude"],
            original_orientation=row["original_orientation"],
            original_capture_datetime=original_capture_datetime,
            original_date_source=DateSource(
                row["original_date_source"]
            ),
            original_latitude=row["original_latitude"],
            original_longitude=row["original_longitude"],
            place_name=row["place_name"],
            city=row["city"],
            address=row["address"],
            raw_location_data=(
                json.loads(row["raw_location_data"])
                if row["raw_location_data"] is not None
                else None
            ),
            location_source=LocationSource(
                row["location_source"]
            ),
            selected_location_components=tuple(
                LocationComponent(
                    key=item["key"],
                    value=item["value"],
                )
                for item in (
                    json.loads(
                        row["selected_location_components"]
                    )
                    if row["selected_location_components"] is not None
                    else []
                )
            ),
            location_text=row["location_text"],
            location_selection_edited=bool(
                row["location_selection_edited"]
            ),
            caption=row["caption"],
        )
