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
    ScanProgress,
    ScanProgressPhase,
)
from photoalbum.sources import (
    PhotoMetadataPolicy,
    resolve_photo_metadata,
)


EventCallback = Callable[[ProcessingEvent], None]
PhaseProgressCallback = Callable[[ScanProgress], None]


class ProjectScanService:
    def scan(
        self,
        *,
        project_path: Path,
        source_directory: Path,
        recursive: bool = False,
        language: str | None = None,
        metadata_policy: PhotoMetadataPolicy | None = None,
        user_agent: str | None = None,
        on_event: EventCallback | None = None,
        on_discovered: Callable[[int], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
        on_phase_progress: PhaseProgressCallback | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> LibraryScanResult:
        database = ProjectDatabase(project_path)

        try:
            database.initialize()
            repository = PhotoRepository(database)

            metadata_processor = PhotoProcessor()

            scanner = LibraryScanner(
                photo_repository=repository,
                photo_processor=metadata_processor,
            )

            def metadata_progress(current: int, total: int) -> None:
                if on_progress is not None:
                    on_progress(current, total)

                if on_phase_progress is not None:
                    on_phase_progress(
                        ScanProgress(
                            phase=ScanProgressPhase.METADATA,
                            current=current,
                            total=total,
                        )
                    )

            result = scanner.scan(
                source_directory,
                recursive=recursive,
                language=language,
                on_event=on_event,
                on_discovered=on_discovered,
                on_progress=metadata_progress,
                should_cancel=should_cancel,
            )

            if result.cancelled:
                return result

            photos = [
                *result.photos,
                *result.date_anomalies,
            ]

            if metadata_policy is not None:
                photos = [
                    resolve_photo_metadata(photo, metadata_policy)
                    for photo in photos
                ]

                for photo in photos:
                    repository.save(photo)

            geocode_enabled = (
                metadata_policy is not None
                and metadata_policy.nominatim_enabled
            )

            if geocode_enabled:
                if not user_agent:
                    raise ValueError(
                        "A User-Agent is required when geocoding is enabled."
                    )

                resolver = create_nominatim_location_resolver(
                    database,
                    user_agent=user_agent,
                )
                geocoding_processor = PhotoProcessor(
                    location_resolver=resolver,
                )

                eligible = [
                    photo
                    for photo in photos
                    if LibraryScanner.needs_location_enrichment(photo)
                ]

                total = len(eligible)

                if on_phase_progress is not None:
                    on_phase_progress(
                        ScanProgress(
                            phase=ScanProgressPhase.NOMINATIM,
                            current=0,
                            total=total,
                        )
                    )

                for index, photo in enumerate(eligible, start=1):
                    if should_cancel is not None and should_cancel():
                        result.cancelled = True
                        break

                    changed = geocoding_processor.enrich_location(
                        photo,
                        language=language,
                        on_event=on_event,
                    )

                    if changed:
                        result.statistics.geocoded += 1

                    if metadata_policy is not None:
                        photo = resolve_photo_metadata(
                            photo,
                            metadata_policy,
                        )

                    repository.save(photo)

                    if on_phase_progress is not None:
                        on_phase_progress(
                            ScanProgress(
                                phase=ScanProgressPhase.NOMINATIM,
                                current=index,
                                total=total,
                            )
                        )

            if metadata_policy is not None:
                # Reload the persisted effective state after both phases.
                photos = [
                    repository.find_by_path(photo.path)
                    for photo in photos
                    if photo.path is not None
                ]
                photos = [
                    photo
                    for photo in photos
                    if photo is not None
                ]

            result.photos = [
                photo
                for photo in photos
                if not photo.is_date_anomaly
            ]
            result.date_anomalies = [
                photo
                for photo in photos
                if photo.is_date_anomaly
            ]

            result.photos.sort(
                key=lambda photo: photo.capture_datetime
            )

            result.statistics.date_anomalies = len(
                result.date_anomalies
            )

            return result

        finally:
            database.close()
