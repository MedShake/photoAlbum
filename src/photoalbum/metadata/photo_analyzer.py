from __future__ import annotations

from pathlib import Path

from photoalbum.models import DateSource, Photo

from .exif_reader import ExifReader
from .filename_date_parser import FilenameDateParser


class PhotoAnalyzer:
    def __init__(
        self,
        exif_reader: ExifReader | None = None,
        filename_date_parser: FilenameDateParser | None = None,
    ) -> None:
        self._exif_reader = exif_reader or ExifReader()
        self._filename_date_parser = (
            filename_date_parser or FilenameDateParser()
        )

    def analyze(self, path: Path) -> Photo:
        file_stat = path.stat()
        metadata = self._exif_reader.read(path)

        capture_datetime = metadata.capture_datetime
        date_source = DateSource.UNKNOWN

        if capture_datetime is not None:
            date_source = DateSource.EXIF
        else:
            capture_datetime = self._filename_date_parser.parse(path.name)

            if capture_datetime is not None:
                date_source = DateSource.FILENAME

        return Photo(
            path=path,
            filename=path.name,
            file_size=file_stat.st_size,
            modified_time_ns=file_stat.st_mtime_ns,
            width=metadata.width,
            height=metadata.height,
            orientation=metadata.orientation,
            capture_datetime=capture_datetime,
            date_source=date_source,
            latitude=metadata.latitude,
            longitude=metadata.longitude,
        )