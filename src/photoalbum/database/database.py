from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class ProjectDatabase:
    """
    SQLite database attached to a single photo album project.

    Schema upgrades are performed in place so projects remain reproducible.
    """

    CURRENT_SCHEMA_VERSION = 4

    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        self._create_schema_version_table()
        self._create_project_metadata_table()
        self._create_geocoding_cache_table()
        version = self._schema_version()

        if version > self.CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Project schema {version} is newer than supported "
                f"schema {self.CURRENT_SCHEMA_VERSION}."
            )

        started_transaction = not self.connection.in_transaction
        if started_transaction:
            self.connection.execute("BEGIN")

        try:
            if not self._table_exists("photos"):
                self._create_photos_table()
            else:
                if version < 2:
                    self._migrate_photos_to_asset_identity()

                if version < 3:
                    self._migrate_photo_metadata_candidates()

                if version < 4:
                    self._migrate_generic_metadata_candidates()

            self._set_schema_version(self.CURRENT_SCHEMA_VERSION)
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

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
                path TEXT UNIQUE,
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

                is_missing INTEGER NOT NULL DEFAULT 0
            )
            """
        )

    def _migrate_generic_metadata_candidates(self) -> None:
        """Keep v3 data while adding extensible candidates and manual state."""
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(photos)")
        }
        additions = (
            ("metadata_candidates", "TEXT NOT NULL DEFAULT '{}'"),
            ("manual_capture_datetime", "TEXT"),
            ("manual_latitude", "REAL"),
            ("manual_longitude", "REAL"),
            ("manual_location_data", "TEXT"),
        )
        for name, definition in additions:
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE photos ADD COLUMN {name} {definition}"
                )

        rows = self.connection.execute("SELECT * FROM photos").fetchall()
        for row in rows:
            dates: dict[str, str] = {}
            gps: dict[str, dict[str, float]] = {}
            locations: dict[str, object] = {}
            captions: dict[str, str] = {}

            if row["exif_capture_datetime"] is not None:
                dates["exif"] = row["exif_capture_datetime"]
            if row["source_capture_datetime"] is not None:
                dates["provider"] = row["source_capture_datetime"]
            if (
                row["original_date_source"] == "filename"
                and row["original_capture_datetime"] is not None
            ):
                dates["filename"] = row["original_capture_datetime"]
            if (
                row["exif_latitude"] is not None
                and row["exif_longitude"] is not None
            ):
                gps["exif"] = {
                    "latitude": row["exif_latitude"],
                    "longitude": row["exif_longitude"],
                }
            if (
                row["source_latitude"] is not None
                and row["source_longitude"] is not None
            ):
                gps["provider"] = {
                    "latitude": row["source_latitude"],
                    "longitude": row["source_longitude"],
                }
            for key, column in (
                ("provider", "source_location_data"),
                ("geocoding", "geocoded_location_data"),
            ):
                if row[column] is not None:
                    try:
                        locations[key] = json.loads(row[column])
                    except (TypeError, ValueError):
                        pass
            if row["imported_caption"]:
                captions["provider"] = row["imported_caption"]

            manual_location = None
            if row["location_source"] == "manual":
                raw = None
                if row["raw_location_data"] is not None:
                    try:
                        raw = json.loads(row["raw_location_data"])
                    except (TypeError, ValueError):
                        pass
                manual_location = json.dumps(
                    {
                        "place_name": row["place_name"],
                        "city": row["city"],
                        "address": row["address"],
                        "raw": raw,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

            self.connection.execute(
                """
                UPDATE photos
                SET metadata_candidates = ?,
                    manual_capture_datetime = CASE
                        WHEN date_source = 'manual' THEN capture_datetime
                        ELSE manual_capture_datetime END,
                    manual_latitude = CASE
                        WHEN gps_source = 'manual' THEN latitude
                        ELSE manual_latitude END,
                    manual_longitude = CASE
                        WHEN gps_source = 'manual' THEN longitude
                        ELSE manual_longitude END,
                    manual_location_data = COALESCE(?, manual_location_data)
                WHERE id = ?
                """,
                (
                    json.dumps(
                        {
                            "date": dates,
                            "gps": gps,
                            "location": locations,
                            "caption": captions,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    manual_location,
                    row["id"],
                ),
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

    def _migrate_photos_to_asset_identity(self) -> None:
        """Upgrade v1 path identities without changing editorial data."""
        self.connection.execute("ALTER TABLE photos RENAME TO photos_v1")
        self._create_photos_table()
        old_columns = [
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(photos_v1)")
        ]
        shared = [
            name for name in old_columns
            if name not in {"id", "path"}
        ]
        columns = ", ".join(shared)
        self.connection.execute(
            f"""
            INSERT INTO photos (
                id, asset_key, source_id, asset_id, path, {columns}
            )
            SELECT
                id, 'local:' || path, 'local', path, path, {columns}
            FROM photos_v1
            """
        )
        self.connection.execute("DROP TABLE photos_v1")

    def _migrate_photo_metadata_candidates(self) -> None:
        """Add independent metadata candidates without changing effective data."""
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(photos)")
        }

        additions = (
            ("exif_capture_datetime", "TEXT"),
            ("source_capture_datetime", "TEXT"),
            ("exif_latitude", "REAL"),
            ("exif_longitude", "REAL"),
            ("source_latitude", "REAL"),
            ("source_longitude", "REAL"),
            (
                "gps_source",
                "TEXT NOT NULL DEFAULT 'unknown'",
            ),
            ("source_location_data", "TEXT"),
            ("geocoded_location_data", "TEXT"),
        )

        for name, definition in additions:
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE photos ADD COLUMN {name} {definition}"
                )

        # Local projects historically obtain their original metadata from the
        # source file. Only an actual EXIF date is promoted to the EXIF
        # candidate; filename-derived dates deliberately remain separate.
        self.connection.execute(
            """
            UPDATE photos
            SET
                exif_capture_datetime = CASE
                    WHEN source_id = 'local'
                         AND original_date_source = 'exif'
                    THEN original_capture_datetime
                    ELSE exif_capture_datetime
                END,
                exif_latitude = CASE
                    WHEN source_id = 'local'
                    THEN original_latitude
                    ELSE exif_latitude
                END,
                exif_longitude = CASE
                    WHEN source_id = 'local'
                    THEN original_longitude
                    ELSE exif_longitude
                END
            """
        )

        # Existing remote snapshots contain provider values in the historical
        # "original" fields. Preserve them as source candidates. This does not
        # alter the effective metadata used by the album.
        self.connection.execute(
            """
            UPDATE photos
            SET
                source_capture_datetime = CASE
                    WHEN source_id <> 'local'
                    THEN original_capture_datetime
                    ELSE source_capture_datetime
                END,
                source_latitude = CASE
                    WHEN source_id <> 'local'
                    THEN original_latitude
                    ELSE source_latitude
                END,
                source_longitude = CASE
                    WHEN source_id <> 'local'
                    THEN original_longitude
                    ELSE source_longitude
                END
            """
        )

        self.connection.execute(
            """
            UPDATE photos
            SET gps_source = CASE
                WHEN latitude IS NULL OR longitude IS NULL
                    THEN 'unknown'
                WHEN location_source = 'manual'
                    THEN 'manual'
                WHEN source_id = 'local'
                    THEN 'exif'
                ELSE 'source'
            END
            """
        )

        # Preserve already-resolved geographic information as an independent
        # geocoding candidate. No resolver or network access is involved.
        rows = self.connection.execute(
            """
            SELECT
                id,
                latitude,
                longitude,
                place_name,
                city,
                address,
                raw_location_data
            FROM photos
            WHERE
                location_source = 'geocoding'
                AND geocoded_location_data IS NULL
            """
        ).fetchall()

        for row in rows:
            raw_data = None
            if row["raw_location_data"] is not None:
                try:
                    raw_data = json.loads(row["raw_location_data"])
                except (TypeError, ValueError):
                    raw_data = None

            payload = {
                "provider": "nominatim",
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "place_name": row["place_name"],
                "city": row["city"],
                "address": row["address"],
                "raw": raw_data,
            }

            self.connection.execute(
                """
                UPDATE photos
                SET geocoded_location_data = ?
                WHERE id = ?
                """,
                (
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    row["id"],
                ),
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
                address TEXT,
                raw_data TEXT
            )
            """
        )
