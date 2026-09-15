from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from photoalbum.database import PhotoRepository
from photoalbum.metadata import PhotoAnalyzer
from photoalbum.models import LocationSource, Photo

from .folder_scanner import FolderScanner
from .photo_processor import (
    EventCallback,
    PhotoProcessor,
)


@dataclass
class ScanError:
    path: Path
    message: str

@dataclass
class ScanStatistics:
    discovered: int = 0
    analyzed: int = 0
    reused: int = 0
    geocoded: int = 0
    date_anomalies: int = 0
    errors: int = 0
    missing: int = 0

@dataclass
class LibraryScanResult:
    photos: list[Photo] = field(default_factory=list)
    date_anomalies: list[Photo] = field(default_factory=list)
    errors: list[ScanError] = field(default_factory=list)
    missing_photos: list[Photo] = field(
        default_factory=list
    )
    statistics: ScanStatistics = field(
        default_factory=ScanStatistics
    )
    @property
    def total_photos(self) -> int:
        return len(self.photos) + len(self.date_anomalies)


class LibraryScanner:
    def __init__(
        self,
        folder_scanner: FolderScanner | None = None,
        photo_analyzer: PhotoAnalyzer | None = None,
        photo_repository: PhotoRepository | None = None,
        photo_processor: PhotoProcessor | None = None,
    ) -> None:
        self._folder_scanner = folder_scanner or FolderScanner()
        self._photo_repository = photo_repository

        self._photo_processor = (
            photo_processor
            or PhotoProcessor(
                photo_analyzer=photo_analyzer or PhotoAnalyzer()
            )
        )

    def scan(
        self,
        directory: Path,
        recursive: bool = False,
        *,
        language: str | None = None,
        on_event: EventCallback | None = None,
    ) -> LibraryScanResult:
        result = LibraryScanResult()

        image_paths = self._folder_scanner.scan(
            directory,
            recursive=recursive,
        )
        result.statistics.discovered = len(image_paths)

        for path in image_paths:
            try:
                photo = self._get_or_process_photo(
                    path,
                    language=language,
                    on_event=on_event,
                    statistics=result.statistics,
                )

            except Exception as exc:
                result.errors.append(
                    ScanError(
                        path=path,
                        message=str(exc),
                    )
                )
                result.statistics.errors += 1
                continue

            if photo.is_date_anomaly:
                result.date_anomalies.append(photo)
                result.statistics.date_anomalies += 1
            else:
                result.photos.append(photo)

        self._synchronize_missing_photos(
            image_paths,
            result,
        )

        result.photos.sort(
            key=lambda photo: photo.capture_datetime
        )

        return result

    def _synchronize_missing_photos(
        self,
        image_paths: list[Path],
        result: LibraryScanResult,
    ) -> None:
        if self._photo_repository is None:
            return

        discovered_paths = {
            str(path)
            for path in image_paths
        }

        known_photos = (
            self._photo_repository.list_all(
                include_missing=True
            )
        )

        for photo in known_photos:
            path_key = str(photo.path)

            if path_key in discovered_paths:
                # Also reactivates a previously missing photo
                # that has returned unchanged and was therefore
                # reused from the cache.
                self._photo_repository.set_missing(
                    photo.path,
                    False,
                )
                continue

            # Do not report the same disappearance on every scan.
            # list_all(include_missing=True) returns both states,
            # so inspect the database state before changing it.
            if self._photo_repository.is_missing(
                photo.path
            ):
                continue

            self._photo_repository.set_missing(
                photo.path,
                True,
            )

            result.missing_photos.append(
                photo
            )
            result.statistics.missing += 1

    def _get_or_process_photo(
        self,
        path: Path,
        *,
        language: str | None,
        on_event: EventCallback | None,
        statistics: ScanStatistics,
    ) -> Photo:
        cached_photo = self._find_current_cached_photo(path)

        if cached_photo is not None:
            statistics.reused += 1

            if self._needs_location_enrichment(cached_photo):
                changed = self._photo_processor.enrich_location(
                    cached_photo,
                    language=language,
                    on_event=on_event,
                )

                if changed:
                    statistics.geocoded += 1

                    if self._photo_repository is not None:
                        self._photo_repository.save(cached_photo)

            return cached_photo

        photo = self._photo_processor.process(
            path,
            language=language,
            on_event=on_event,
        )

        statistics.analyzed += 1

        if photo.location_source == LocationSource.GEOCODING:
            statistics.geocoded += 1

        if self._photo_repository is not None:
            self._photo_repository.save(photo)

        return photo

    def _find_current_cached_photo(
        self,
        path: Path,
    ) -> Photo | None:
        if self._photo_repository is None:
            return None

        cached_photo = self._photo_repository.find_by_path(path)

        if cached_photo is None:
            return None

        file_stat = path.stat()

        if (
            cached_photo.file_size == file_stat.st_size
            and cached_photo.modified_time_ns
            == file_stat.st_mtime_ns
        ):
            return cached_photo

        return None

    @staticmethod
    def _needs_location_enrichment(
        photo: Photo,
    ) -> bool:
        return (
            photo.has_gps
            and photo.location_source
            == LocationSource.UNKNOWN
        )