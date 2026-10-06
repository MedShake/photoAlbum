from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
from photoalbum.geocoding import GeocodingError, LocationResolver
from photoalbum.geocoding.location_resolver import (
    LocationResolutionSource,
)
from photoalbum.metadata import PhotoAnalyzer
from photoalbum.models import (
    DateSource,
    Location,
    LocationSource,
    Photo,
)

from .processing_event import (
    ProcessingEvent,
    ProcessingEventType,
)


EventCallback = Callable[[ProcessingEvent], None]


class PhotoProcessor:
    def __init__(
        self,
        photo_analyzer: PhotoAnalyzer | None = None,
        location_resolver: LocationResolver | None = None,
    ) -> None:
        self._photo_analyzer = photo_analyzer or PhotoAnalyzer()
        self._location_resolver = location_resolver

    def process(
        self,
        path: Path,
        *,
        language: str | None = None,
        on_event: EventCallback | None = None,
    ) -> Photo:
        self._emit(
            on_event,
            ProcessingEventType.ANALYSIS_STARTED,
            path,
            "Photo analysis started.",
        )

        photo = self._photo_analyzer.analyze(path)

        self._emit_date_event(photo, on_event)

        if photo.has_gps:
            self._emit(
                on_event,
                ProcessingEventType.GPS_FOUND,
                path,
                "GPS coordinates found.",
            )
        else:
            self._emit(
                on_event,
                ProcessingEventType.GPS_MISSING,
                path,
                "No GPS coordinates found.",
            )

        self._emit(
            on_event,
            ProcessingEventType.ANALYSIS_COMPLETED,
            path,
            "Photo analysis completed.",
        )

        return photo

    def enrich_location(
        self,
        photo: Photo,
        *,
        language: str | None = None,
        on_event: EventCallback | None = None,
    ) -> bool:
        if not photo.has_gps:
            return False

        if self._location_resolver is None:
            return False

        self._emit(
            on_event,
            ProcessingEventType.GEOCODING_STARTED,
            photo.path,
            "Resolving geographic information.",
        )

        try:
            resolution = self._location_resolver.resolve_with_source(
                photo.latitude,
                photo.longitude,
                language=language,
            )
        except GeocodingError as exc:
            self._emit(
                on_event,
                ProcessingEventType.GEOCODING_ERROR,
                photo.path,
                f"Geocoding failed: {exc}",
            )
            return False

        location = resolution.location

        if location is None:
            self._emit(
                on_event,
                ProcessingEventType.LOCATION_NOT_FOUND,
                photo.path,
                "No geographic information found.",
            )
            return False

        self._apply_location(photo, location)

        if resolution.source == LocationResolutionSource.CACHE:
            event_type = (
                ProcessingEventType.LOCATION_FROM_CACHE
            )
            message = (
                "Geographic information reused from "
                "a nearby cached position."
            )
        else:
            event_type = (
                ProcessingEventType.LOCATION_FROM_REVERSE
            )
            message = (
                "Geographic information obtained by "
                "reverse geocoding."
            )

        self._emit(
            on_event,
            event_type,
            photo.path,
            message,
        )

        return True

    @staticmethod
    def _apply_location(
        photo: Photo,
        location: Location,
    ) -> None:
        # Keep the Nominatim result as an independent candidate tied to
        # the GPS position for which it was resolved.
        photo.geocoded_location_data = {
            "provider": "nominatim",
            "latitude": photo.latitude,
            "longitude": photo.longitude,
            "place_name": location.place_name,
            "city": location.city,
            "address": location.address,
            "raw": location.raw_data,
        }

        # Keep the effective value useful for callers that do not immediately
        # run the project policy. A manual location remains authoritative.
        if photo.location_source == LocationSource.MANUAL:
            return

        photo.place_name = location.place_name
        photo.city = location.city
        photo.address = location.address
        photo.raw_location_data = location.raw_data
        photo.location_source = LocationSource.GEOCODING

    @staticmethod
    def _emit_date_event(
        photo: Photo,
        on_event: EventCallback | None,
    ) -> None:
        if photo.date_source == DateSource.EXIF:
            event_type = ProcessingEventType.DATE_FROM_EXIF
            message = "Capture date found in EXIF metadata."

        elif photo.date_source == DateSource.FILENAME:
            event_type = ProcessingEventType.DATE_FROM_FILENAME
            message = "Capture date found in filename."

        elif photo.date_source == DateSource.MANUAL:
            return

        else:
            event_type = ProcessingEventType.DATE_MISSING
            message = "No capture date could be determined."

        PhotoProcessor._emit(
            on_event,
            event_type,
            photo.path,
            message,
        )

    @staticmethod
    def _emit(
        on_event: EventCallback | None,
        event_type: ProcessingEventType,
        path: Path,
        message: str,
    ) -> None:
        if on_event is None:
            return

        on_event(
            ProcessingEvent(
                type=event_type,
                path=path,
                message=message,
            )
        )
