from datetime import datetime
from pathlib import Path

from photoalbum.models import (
    DateSource,
    Location,
    LocationSource,
    Photo,
)
from photoalbum.scanner import (
    PhotoProcessor,
    ProcessingEventType,
)


class FakeAnalyzer:
    def __init__(self, photo: Photo) -> None:
        self.photo = photo
        self.calls = 0

    def analyze(self, path: Path) -> Photo:
        self.calls += 1
        return self.photo


class FakeLocationResolver:
    def __init__(
        self,
        location: Location | None,
    ) -> None:
        self.location = location
        self.calls = 0
        self.force_refresh_values: list[bool] = []

    def resolve(
        self,
        latitude: float,
        longitude: float,
        *,
        language: str | None = None,
        force_refresh: bool = False,
    ) -> Location | None:
        self.calls += 1
        self.force_refresh_values.append(force_refresh)
        return self.location


def test_photo_without_gps_does_not_use_resolver():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        capture_datetime=datetime(2025, 1, 1),
        date_source=DateSource.EXIF,
    )

    analyzer = FakeAnalyzer(photo)
    resolver = FakeLocationResolver(None)

    processor = PhotoProcessor(
        photo_analyzer=analyzer,
        location_resolver=resolver,
    )

    result = processor.process(photo.path)

    assert result is photo
    assert resolver.calls == 0


def test_photo_with_gps_is_enriched():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        capture_datetime=datetime(2025, 1, 1),
        date_source=DateSource.EXIF,
        latitude=47.2184,
        longitude=-1.5536,
    )

    resolver = FakeLocationResolver(
        Location(
            latitude=47.2184,
            longitude=-1.5536,
            place_name="Example Place",
            city="Nantes",
            address="Example Place, Nantes, France",
        )
    )

    processor = PhotoProcessor(
        photo_analyzer=FakeAnalyzer(photo),
        location_resolver=resolver,
    )

    result = processor.process(photo.path)

    assert result.place_name == "Example Place"
    assert result.city == "Nantes"
    assert result.address == "Example Place, Nantes, France"
    assert result.location_source == LocationSource.GEOCODING


def test_missing_date_emits_anomaly_event():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
    )

    events = []

    processor = PhotoProcessor(
        photo_analyzer=FakeAnalyzer(photo),
    )

    processor.process(
        photo.path,
        on_event=events.append,
    )

    event_types = [event.type for event in events]

    assert ProcessingEventType.DATE_MISSING in event_types


def test_filename_date_emits_filename_event():
    photo = Photo(
        path=Path("/photos/2025-01-01.jpg"),
        filename="2025-01-01.jpg",
        capture_datetime=datetime(2025, 1, 1),
        date_source=DateSource.FILENAME,
    )

    events = []

    processor = PhotoProcessor(
        photo_analyzer=FakeAnalyzer(photo),
    )

    processor.process(
        photo.path,
        on_event=events.append,
    )

    event_types = [event.type for event in events]

    assert ProcessingEventType.DATE_FROM_FILENAME in event_types


def test_location_failure_does_not_mark_photo_as_geocoded():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        latitude=47.2184,
        longitude=-1.5536,
    )

    processor = PhotoProcessor(
        photo_analyzer=FakeAnalyzer(photo),
        location_resolver=FakeLocationResolver(None),
    )

    result = processor.process(photo.path)

    assert result.location_source == LocationSource.UNKNOWN
    assert result.city is None


def test_refresh_location_forces_resolver():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        latitude=47.2184,
        longitude=-1.5536,
        city="Old City",
        location_source=LocationSource.GEOCODING,
    )

    resolver = FakeLocationResolver(
        Location(
            latitude=47.2184,
            longitude=-1.5536,
            city="Fresh City",
        )
    )

    processor = PhotoProcessor(
        location_resolver=resolver,
    )

    refreshed = processor.refresh_location(photo)

    assert refreshed is True
    assert photo.city == "Fresh City"
    assert resolver.force_refresh_values == [True]


def test_failed_refresh_keeps_existing_location():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
        latitude=47.2184,
        longitude=-1.5536,
        city="Existing City",
        location_source=LocationSource.GEOCODING,
    )

    processor = PhotoProcessor(
        location_resolver=FakeLocationResolver(None),
    )

    refreshed = processor.refresh_location(photo)

    assert refreshed is False
    assert photo.city == "Existing City"


def test_processing_emits_start_and_completion_events():
    photo = Photo(
        path=Path("/photos/example.jpg"),
        filename="example.jpg",
    )

    events = []

    processor = PhotoProcessor(
        photo_analyzer=FakeAnalyzer(photo),
    )

    processor.process(
        photo.path,
        on_event=events.append,
    )

    assert events[0].type == ProcessingEventType.ANALYSIS_STARTED
    assert events[-1].type == ProcessingEventType.ANALYSIS_COMPLETED

