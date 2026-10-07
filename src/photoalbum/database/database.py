from __future__ import annotations

import sqlite3
from pathlib import Path
from uuid import uuid4


class ProjectDatabase:
    """
    SQLite database attached to a single photo album project.

    Schema upgrades are performed in place so projects remain reproducible.
    """

    CURRENT_SCHEMA_VERSION = 5

    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        if not self.connection.in_transaction:
            self.connection.execute("BEGIN")
        try:
            self._initialize_schema()
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def _initialize_schema(self) -> None:
        self._create_schema_version_table()
        self._create_project_metadata_table()
        self.connection.execute(
            "INSERT OR IGNORE INTO project_metadata (key, value) VALUES (?, ?)",
            ("cache_project_id", uuid4().hex),
        )
        self._create_geocoding_cache_table()
        version = self._schema_version()

        if version > self.CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Project schema {version} is newer than supported "
                f"schema {self.CURRENT_SCHEMA_VERSION}."
            )

        if version == self.CURRENT_SCHEMA_VERSION:
            return
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                position INTEGER NOT NULL,
                configuration TEXT NOT NULL
            )"""
        )
        if self._table_exists("photos"):
            self._normalize_legacy_project()
        else:
            self._create_photos_table()
        self.connection.execute("CREATE INDEX IF NOT EXISTS photos_path ON photos(path)")
        self._set_schema_version(self.CURRENT_SCHEMA_VERSION)

    def set_project_metadata(
        self,
        key: str,
        value: str,
        *,
        commit: bool = True,
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

        if commit:
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

    def _normalize_legacy_project(self) -> None:
        from .legacy_project import normalize_project
        normalize_project(self)

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
                asset_key TEXT NOT NULL UNIQUE,
                source_id TEXT NOT NULL DEFAULT 'local',
                asset_id TEXT NOT NULL,
                path TEXT,
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

                exif_capture_datetime TEXT,
                source_capture_datetime TEXT,
                exif_latitude REAL,
                exif_longitude REAL,
                source_latitude REAL,
                source_longitude REAL,
                gps_source TEXT NOT NULL DEFAULT 'unknown',

                source_location_data TEXT,
                geocoded_location_data TEXT,

                place_name TEXT,
                city TEXT,
                address TEXT,
                raw_location_data TEXT,
                location_source TEXT NOT NULL DEFAULT 'unknown',

                selected_location_components TEXT,
                location_text TEXT,
                location_selection_edited INTEGER NOT NULL DEFAULT 0,
                caption TEXT,
                imported_location_text TEXT,
                imported_caption TEXT,
                source_metadata TEXT,
                metadata_candidates TEXT NOT NULL DEFAULT '{}',
                manual_capture_datetime TEXT,
                manual_latitude REAL,
                manual_longitude REAL,
                manual_location_data TEXT,

                is_missing INTEGER NOT NULL DEFAULT 0,
                usage TEXT NOT NULL DEFAULT 'body'
                    CHECK (usage IN ('body', 'template_only', 'off'))
            )
            """
        )

    def _schema_version(self) -> int:
        row = self.connection.execute(
            "SELECT version FROM schema_version LIMIT 1"
        ).fetchone()
        return int(row["version"]) if row is not None else 0

    def _table_exists(self, name: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        return row is not None

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
                address TEXT,
                raw_data TEXT
            )
            """
        )
