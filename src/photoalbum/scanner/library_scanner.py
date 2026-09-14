from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from photoalbum.database import PhotoRepository
from photoalbum.metadata import PhotoAnalyzer
from photoalbum.models import Photo

from .folder_scanner import FolderScanner


@dataclass
class ScanError:
    path: Path
    message: str


@dataclass
class LibraryScanResult:
    photos: list[Photo] = field(default_factory=list)
    date_anomalies: list[Photo] = field(default_factory=list)
    errors: list[ScanError] = field(default_factory=list)

    @property
    def total_photos(self) -> int:
        return len(self.photos) + len(self.date_anomalies)


class LibraryScanner:
    def __init__(
        self,
        folder_scanner: FolderScanner | None = None,
        photo_analyzer: PhotoAnalyzer | None = None,
        photo_repository: PhotoRepository | None = None,
    ) -> None:
        self._folder_scanner = folder_scanner or FolderScanner()
        self._photo_analyzer = photo_analyzer or PhotoAnalyzer()
        self._photo_repository = photo_repository

    def scan(
        self,
        directory: Path,
        recursive: bool = False,
    ) -> LibraryScanResult:
        result = LibraryScanResult()

        image_paths = self._folder_scanner.scan(
            directory,
            recursive=recursive,
        )

        for path in image_paths:
            try:
                photo = self._get_or_analyze_photo(path)
            except Exception as exc:
                result.errors.append(
                    ScanError(
                        path=path,
                        message=str(exc),
                    )
                )
                continue

            if photo.is_date_anomaly:
                result.date_anomalies.append(photo)
            else:
                result.photos.append(photo)

        result.photos.sort(
            key=lambda photo: photo.capture_datetime
        )

        return result

    def _get_or_analyze_photo(self, path: Path) -> Photo:
        cached_photo = self._find_current_cached_photo(path)

        if cached_photo is not None:
            return cached_photo

        photo = self._photo_analyzer.analyze(path)

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
            and cached_photo.modified_time_ns == file_stat.st_mtime_ns
        ):
            return cached_photo

        return None