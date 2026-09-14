from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image


@dataclass
class ImageMetadata:
    width: int
    height: int
    orientation: int | None = None
    capture_datetime: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None


class ExifReader:
    def read(self, path: Path) -> ImageMetadata:
        with Image.open(path) as image:
            width, height = image.size
            exif = image.getexif()

            metadata = ImageMetadata(
                width=width,
                height=height,
            )

            if not exif:
                return metadata

            metadata.orientation = self._read_orientation(exif)
            metadata.capture_datetime = self._read_capture_datetime(exif)

            latitude, longitude = self._read_gps(exif)
            metadata.latitude = latitude
            metadata.longitude = longitude

            return metadata

    def _read_orientation(self, exif: Any) -> int | None:
        orientation_tag = self._find_tag_id("Orientation")
        if orientation_tag is None:
            return None

        value = exif.get(orientation_tag)

        if isinstance(value, int):
            return value

        return None

    def _read_capture_datetime(self, exif: Any) -> datetime | None:
        tag_names = (
            "DateTimeOriginal",
            "DateTimeDigitized",
            "DateTime",
        )

        for tag_name in tag_names:
            tag_id = self._find_tag_id(tag_name)
            if tag_id is None:
                continue

            raw_value = exif.get(tag_id)
            parsed = self._parse_exif_datetime(raw_value)

            if parsed is not None:
                return parsed

        return None

    def _read_gps(
        self,
        exif: Any,
    ) -> tuple[float | None, float | None]:
        gps_tag = self._find_tag_id("GPSInfo")
        if gps_tag is None:
            return None, None

        raw_gps = exif.get(gps_tag)
        if raw_gps is None:
            return None, None

        try:
            gps_data = exif.get_ifd(gps_tag)
        except (AttributeError, KeyError, TypeError):
            return None, None

        latitude = self._convert_gps_coordinate(
            gps_data.get(2),
            gps_data.get(1),
        )
        longitude = self._convert_gps_coordinate(
            gps_data.get(4),
            gps_data.get(3),
        )

        return latitude, longitude

    @staticmethod
    def _parse_exif_datetime(value: Any) -> datetime | None:
        if not isinstance(value, str):
            return None

        try:
            return datetime.strptime(
                value.strip(),
                "%Y:%m:%d %H:%M:%S",
            )
        except ValueError:
            return None

    @staticmethod
    def _convert_gps_coordinate(
        coordinate: Any,
        reference: Any,
    ) -> float | None:
        if coordinate is None or reference is None:
            return None

        try:
            degrees = float(coordinate[0])
            minutes = float(coordinate[1])
            seconds = float(coordinate[2])
        except (TypeError, ValueError, IndexError):
            return None

        decimal = degrees + minutes / 60 + seconds / 3600

        reference_text = str(reference).upper()

        if reference_text in {"S", "W"}:
            decimal = -decimal

        return decimal

    @staticmethod
    def _find_tag_id(name: str) -> int | None:
        for tag_id, tag_name in ExifTags.TAGS.items():
            if tag_name == name:
                return tag_id

        return None

