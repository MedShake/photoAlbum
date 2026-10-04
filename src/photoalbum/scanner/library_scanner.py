from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from photoalbum.database import PhotoRepository
from photoalbum.metadata import PhotoAnalyzer
from photoalbum.models import DateSource, GpsSource, LocationSource, Photo

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
    cancelled: bool = False
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
        on_discovered: Callable[[int], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> LibraryScanResult:
        result = LibraryScanResult()

        image_paths = self._folder_scanner.scan(
            directory,
            recursive=recursive,
        )
        result.statistics.discovered = len(image_paths)

        total = len(image_paths)

        if on_discovered is not None:
            on_discovered(total)

        completed = 0

        for path in image_paths:
            if should_cancel is not None and should_cancel():
                break

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
                completed += 1

                if on_progress is not None:
                    on_progress(completed, total)

                continue

            if photo.is_date_anomaly:
                result.date_anomalies.append(photo)
                result.statistics.date_anomalies += 1
            else:
                result.photos.append(photo)

            completed += 1

            if on_progress is not None:
                on_progress(completed, total)

        # Synchronizing missing photos is only valid after a complete
        # traversal.  A cancelled scan must not mark every unvisited
        # photo as missing.
        result.cancelled = completed < total

        if not result.cancelled:
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

    def _get_or_process_photo(
        self,
        path: Path,
        *,
        language: str | None,
        on_event: EventCallback | None,
        statistics: ScanStatistics,
    ) -> Photo:
        previous_photo = (
            self._photo_repository.find_by_path(path)
            if self._photo_repository is not None
            else None
        )

        cached_photo = self._find_current_cached_photo(path)

        if cached_photo is not None:
            statistics.reused += 1

            return cached_photo

        photo = self._photo_processor.process(
            path,
            language=language,
            on_event=on_event,
        )

        statistics.analyzed += 1

        if previous_photo is not None:
            self._preserve_user_state(
                photo,
                previous_photo,
            )

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
    def needs_location_enrichment(
        photo: Photo,
    ) -> bool:
        if not photo.has_gps:
            return False

        candidate = photo.geocoded_location_data

        if not isinstance(candidate, dict):
            return True

        latitude = candidate.get("latitude")
        longitude = candidate.get("longitude")

        if not isinstance(latitude, (int, float)):
            return True
        if not isinstance(longitude, (int, float)):
            return True

        tolerance = 1e-7

        return not (
            abs(photo.latitude - float(latitude)) <= tolerance
            and abs(photo.longitude - float(longitude)) <= tolerance
        )

    @staticmethod
    def _preserve_user_state(
        photo: Photo,
        previous: Photo,
    ) -> None:
        """Keep user-authored state while refreshing source metadata."""

        if previous.date_source == DateSource.MANUAL:
            photo.capture_datetime = previous.capture_datetime
            photo.date_source = DateSource.MANUAL

        if previous.gps_source == GpsSource.MANUAL:
            photo.latitude = previous.latitude
            photo.longitude = previous.longitude
            photo.gps_source = GpsSource.MANUAL

        if previous.location_source == LocationSource.MANUAL:
            photo.place_name = previous.place_name
            photo.city = previous.city
            photo.address = previous.address
            photo.raw_location_data = previous.raw_location_data
            photo.location_source = LocationSource.MANUAL

        # Editorial choices are independent from source analysis.
        photo.selected_location_components = (
            previous.selected_location_components
        )
        photo.location_text = previous.location_text
        photo.location_selection_edited = (
            previous.location_selection_edited
        )
        photo.caption = previous.caption

        # A prior Nominatim result remains a candidate even if a changed
        # file now carries different GPS coordinates. The policy resolver
        # will reject it as stale until enrichment refreshes it.
        if photo.geocoded_location_data is None:
            photo.geocoded_location_data = (
                previous.geocoded_location_data
            )
