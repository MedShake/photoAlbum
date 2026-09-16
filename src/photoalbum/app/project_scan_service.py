from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from photoalbum.database import PhotoRepository, ProjectDatabase
from photoalbum.geocoding import create_nominatim_location_resolver
from photoalbum.scanner import (
    LibraryScanResult,
    LibraryScanner,
    PhotoProcessor,
    ProcessingEvent,
)


EventCallback = Callable[[ProcessingEvent], None]


class ProjectScanService:
    def scan(
        self,
        *,
        project_path: Path,
        source_directory: Path,
        recursive: bool = False,
        language: str | None = None,
        geocode: bool = False,
        user_agent: str | None = None,
        on_event: EventCallback | None = None,
        on_discovered: Callable[[int], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> LibraryScanResult:
        database = ProjectDatabase(project_path)

        try:
            database.initialize()

            repository = PhotoRepository(database)

            if geocode:
                if not user_agent:
                    raise ValueError(
                        "A User-Agent is required when geocoding is enabled."
                    )

                resolver = create_nominatim_location_resolver(
                    database,
                    user_agent=user_agent,
                )

                processor = PhotoProcessor(
                    location_resolver=resolver,
                )
            else:
                processor = PhotoProcessor()

            scanner = LibraryScanner(
                photo_repository=repository,
                photo_processor=processor,
            )

            return scanner.scan(
                source_directory,
                recursive=recursive,
                language=language,
                on_event=on_event,
                on_discovered=on_discovered,
                on_progress=on_progress,
                should_cancel=should_cancel,
            )

        finally:
            database.close()