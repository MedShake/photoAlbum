from __future__ import annotations

from dataclasses import replace

from photoalbum.sources.config import ProjectSource
from .database import ProjectDatabase


class SourceRepository:
    """The ordered, persistent collection of configured source occurrences."""

    def __init__(self, database: ProjectDatabase) -> None:
        self._database = database

    def list_all(self) -> list[ProjectSource]:
        return [ProjectSource.from_json(row["configuration"]) for row in
                self._database.connection.execute(
                    "SELECT configuration FROM sources ORDER BY position, source_id")]

    def find(self, source_id: str) -> ProjectSource | None:
        row = self._database.connection.execute(
            "SELECT configuration FROM sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        return ProjectSource.from_json(row[0]) if row else None

    def save(self, source: ProjectSource, *, commit: bool = True) -> None:
        self._database.connection.execute(
            """INSERT INTO sources(source_id, position, configuration)
               VALUES (?, (SELECT COALESCE(MAX(position), -1) + 1 FROM sources), ?)
               ON CONFLICT(source_id) DO UPDATE SET configuration=excluded.configuration""",
            (source.id, source.to_json()),
        )
        if commit:
            self._database.connection.commit()

    def set_enabled(self, source_id: str, enabled: bool) -> None:
        source = self.find(source_id)
        if source is None:
            raise KeyError(source_id)
        self.save(replace(source, enabled=enabled))

    def delete(self, source_id: str) -> None:
        # No cross-source cascades: the snapshot and configuration are one unit.
        with self._database.connection:
            self._database.connection.execute(
                "DELETE FROM photos WHERE source_id = ?", (source_id,))
            self._database.connection.execute(
                "DELETE FROM sources WHERE source_id = ?", (source_id,))
