from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def initialize(self) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
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
                place_name TEXT,
                city TEXT,
                address TEXT
            )
            """
        )

        self.connection.commit()