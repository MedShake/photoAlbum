from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
from photoalbum.geocoding import GeocodingError, LocationResolver
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

            self.enrich_location(
                photo,
                language=language,
                on_event=on_event,
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
        force_refresh: bool = False,
    ) -> bool:
        if not photo.has_gps:
            return False

        if self._location_resolver is None:
            return False

        if (
            photo.location_source == LocationSource.MANUAL
            and not force_refresh
        ):
            return False

        self._emit(
            on_event,
            ProcessingEventType.GEOCODING_STARTED,
            photo.path,
            "Resolving geographic information.",
        )

        try:
            location = self._location_resolver.resolve(
                photo.latitude,
                photo.longitude,
                language=language,
                force_refresh=force_refresh,
            )
        except GeocodingError as exc:
            self._emit(
                on_event,
                ProcessingEventType.GEOCODING_ERROR,
                photo.path,
                f"Geocoding failed: {exc}",
            )
            return False

        if location is None:
            self._emit(
                on_event,
                ProcessingEventType.LOCATION_NOT_FOUND,
                photo.path,
                "No geographic information found.",
            )
            return False

        self._apply_location(photo, location)

        message = (
            "Geographic information refreshed."
            if force_refresh
            else "Geographic information resolved."
        )

        self._emit(
            on_event,
            ProcessingEventType.LOCATION_RESOLVED,
            photo.path,
            message,
        )

        return True

    def refresh_location(
        self,
        photo: Photo,
        *,
        language: str | None = None,
        on_event: EventCallback | None = None,
    ) -> bool:
        return self.enrich_location(
            photo,
            language=language,
            on_event=on_event,
            force_refresh=True,
        )

    @staticmethod
    def _apply_location(
        photo: Photo,
        location: Location,
    ) -> None:
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