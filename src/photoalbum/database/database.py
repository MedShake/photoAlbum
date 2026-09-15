from __future__ import annotations

import sqlite3
from pathlib import Path


class ProjectDatabase:
    """
    SQLite database attached to a single photo album project.

    During early development, the schema may still change directly.
    Migration support will be introduced before the first stable release.
    """

    CURRENT_SCHEMA_VERSION = 1

    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        self._create_schema_version_table()
        self._create_project_metadata_table()
        self._create_photos_table()
        self._create_geocoding_cache_table()
        self._set_schema_version(self.CURRENT_SCHEMA_VERSION)

        self.connection.commit()

    def get_schema_version(self) -> int:
        row = self.connection.execute(
            """
            SELECT version
            FROM schema_version
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            return 0

        return int(row["version"])

    def set_project_metadata(
        self,
        key: str,
        value: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO project_metadata (
                key,
                value
            )
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value
            """,
            (key, value),
        )

        self.connection.commit()

    def get_project_metadata(
        self,
        key: str,
    ) -> str | None:
        row = self.connection.execute(
            """
            SELECT value
            FROM project_metadata
            WHERE key = ?
            """,
            (key,),
        ).fetchone()

        if row is None:
            return None

        return str(row["value"])

    def _create_schema_version_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            )
            """
        )

    def _create_project_metadata_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    def _create_photos_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                file_size INTEGER,
                modified_time_ns INTEGER,
                content_hash TEXT,
                width INTEGER,
                height INTEGER,

                orientation INTEGER,
                capture_datetime TEXT,
                date_source TEXT NOT NULL,
                latitude REAL,
                longitude REAL,

                original_orientation INTEGER,
                original_capture_datetime TEXT,
                original_date_source TEXT NOT NULL,
                original_latitude REAL,
                original_longitude REAL,

                place_name TEXT,
                city TEXT,
                address TEXT,
                location_source TEXT NOT NULL DEFAULT 'unknown',
                is_missing INTEGER NOT NULL DEFAULT 0
            )
            """
        )

    def _set_schema_version(
        self,
        version: int,
    ) -> None:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM schema_version
            """
        ).fetchone()

        if row["count"] == 0:
            self.connection.execute(
                """
                INSERT INTO schema_version (
                    version
                )
                VALUES (?)
                """,
                (version,),
            )
        else:
            self.connection.execute(
                """
                UPDATE schema_version
                SET version = ?
                """,
                (version,),
            )

    def _create_geocoding_cache_table(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                place_name TEXT,
                city TEXT,
                address TEXT
            )
            """
        )
