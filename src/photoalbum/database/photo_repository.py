from __future__ import annotations

from datetime import datetime
from pathlib import Path

from photoalbum.models import DateSource, Photo

from .database import Database


class PhotoRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def save(self, photo: Photo) -> None:
        capture_datetime = (
            photo.capture_datetime.isoformat()
            if photo.capture_datetime is not None
            else None
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
                place_name,
                city,
                address
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                place_name = excluded.place_name,
                city = excluded.city,
                address = excluded.address
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
                photo.place_name,
                photo.city,
                photo.address,
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

    def list_all(self) -> list[Photo]:
        rows = self._database.connection.execute(
            """
            SELECT *
            FROM photos
            ORDER BY capture_datetime, filename
            """
        ).fetchall()

        return [
            self._row_to_photo(row)
            for row in rows
        ]

    @staticmethod
    def _row_to_photo(row) -> Photo:
        capture_datetime = (
            datetime.fromisoformat(row["capture_datetime"])
            if row["capture_datetime"] is not None
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
            place_name=row["place_name"],
            city=row["city"],
            address=row["address"],
        )