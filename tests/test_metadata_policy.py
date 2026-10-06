from datetime import datetime
from pathlib import Path

from photoalbum.models import (
    DateSource,
    GpsSource,
    LocationComponent,
    LocationSource,
    Photo,
)
from photoalbum.sources import (
    PhotoMetadataPolicy,
    resolve_photo_metadata,
)


def policy(
    *,
    date="source",
    gps="source",
    location="source",
    nominatim=False,
):
    return PhotoMetadataPolicy(
        date_preference=date,
        gps_preference=gps,
        location_preference=location,
        nominatim_enabled=nominatim,
    )


def test_policy_uses_requested_source_candidates():
    source_date = datetime(2024, 7, 1, 12, 30)

    photo = Photo(
        path=Path("/photos/photo.jpg"),
        filename="photo.jpg",
        exif_capture_datetime=datetime(2024, 6, 1, 8, 0),
        source_capture_datetime=source_date,
        exif_latitude=47.0,
        exif_longitude=-1.0,
        source_latitude=48.0,
        source_longitude=2.0,
        source_location_data={
            "provider": "synology",
            "place_name": "Provider place",
            "city": "Paris",
            "address": "Paris, France",
            "raw": {"city": "Paris"},
        },
    )

    resolved = resolve_photo_metadata(photo, policy())

    assert resolved.capture_datetime == source_date
    assert resolved.date_source == DateSource.SOURCE
    assert (resolved.latitude, resolved.longitude) == (48.0, 2.0)
    assert resolved.gps_source == GpsSource.SOURCE
    assert resolved.place_name == "Provider place"
    assert resolved.city == "Paris"
    assert resolved.location_source == LocationSource.SOURCE

    # Candidates are not consumed or rewritten.
    assert resolved.exif_capture_datetime == photo.exif_capture_datetime
    assert resolved.source_capture_datetime == photo.source_capture_datetime
    assert resolved.exif_latitude == 47.0
    assert resolved.source_latitude == 48.0


def test_policy_falls_back_when_requested_candidate_is_missing():
    exif_date = datetime(2023, 5, 4, 10, 0)

    photo = Photo(
        path=Path("/photos/photo.jpg"),
        filename="photo.jpg",
        exif_capture_datetime=exif_date,
        exif_latitude=47.2,
        exif_longitude=-1.5,
    )

    resolved = resolve_photo_metadata(
        photo,
        policy(
            date="source",
            gps="source",
            location="source",
        ),
    )

    assert resolved.capture_datetime == exif_date
    assert resolved.date_source == DateSource.EXIF
    assert (resolved.latitude, resolved.longitude) == (47.2, -1.5)
    assert resolved.gps_source == GpsSource.EXIF


def test_manual_effective_values_are_preserved():
    manual_date = datetime(2025, 1, 2, 3, 4)

    photo = Photo(
        path=Path("/photos/photo.jpg"),
        filename="photo.jpg",
        capture_datetime=manual_date,
        date_source=DateSource.MANUAL,
        latitude=45.0,
        longitude=4.0,
        gps_source=GpsSource.MANUAL,
        source_capture_datetime=datetime(2020, 1, 1),
        source_latitude=48.0,
        source_longitude=2.0,
        place_name=None,
        city=None,
        address=None,
        location_source=LocationSource.MANUAL,
        source_location_data={
            "provider": "synology",
            "city": "Paris",
            "address": "Paris, France",
        },
    )

    resolved = resolve_photo_metadata(photo, policy())

    assert resolved.capture_datetime == manual_date
    assert resolved.date_source == DateSource.MANUAL
    assert (resolved.latitude, resolved.longitude) == (45.0, 4.0)
    assert resolved.gps_source == GpsSource.MANUAL
    assert resolved.location_source == LocationSource.MANUAL
    assert resolved.city is None


def test_geocoded_candidate_must_match_effective_gps():
    photo = Photo(
        path=Path("/photos/photo.jpg"),
        filename="photo.jpg",
        source_latitude=48.0,
        source_longitude=2.0,
        source_location_data={
            "provider": "synology",
            "city": "Paris",
            "address": "Paris, France",
        },
        geocoded_location_data={
            "provider": "nominatim",
            "latitude": 47.0,
            "longitude": -1.0,
            "city": "Nantes",
            "address": "Nantes, France",
        },
    )

    resolved = resolve_photo_metadata(
        photo,
        policy(location="geocoding"),
    )

    assert (resolved.latitude, resolved.longitude) == (48.0, 2.0)

    # Stale Nominatim is ignored, then the source location is used as fallback.
    assert resolved.city == "Paris"
    assert resolved.location_source == LocationSource.SOURCE


def test_matching_geocoded_candidate_can_be_used_even_when_network_is_disabled():
    photo = Photo(
        path=Path("/photos/photo.jpg"),
        filename="photo.jpg",
        exif_latitude=47.2184,
        exif_longitude=-1.5536,
        geocoded_location_data={
            "provider": "nominatim",
            "latitude": 47.2184,
            "longitude": -1.5536,
            "place_name": "Example Place",
            "city": "Nantes",
            "address": "Example Place, Nantes, France",
            "raw": {"address": {"city": "Nantes"}},
        },
    )

    resolved = resolve_photo_metadata(
        photo,
        policy(
            gps="exif",
            location="geocoding",
            nominatim=False,
        ),
    )

    assert resolved.city == "Nantes"
    assert resolved.location_source == LocationSource.GEOCODING


def test_none_location_clears_only_effective_automatic_location():
    components = (
        LocationComponent(key="city", value="My editorial city"),
    )
    source_candidate = {
        "provider": "synology",
        "city": "Paris",
        "address": "Paris, France",
    }
    geocoded_candidate = {
        "provider": "nominatim",
        "latitude": 48.0,
        "longitude": 2.0,
        "city": "Nantes",
    }

    photo = Photo(
        path=Path("/photos/photo.jpg"),
        filename="photo.jpg",
        source_latitude=48.0,
        source_longitude=2.0,
        source_location_data=source_candidate,
        geocoded_location_data=geocoded_candidate,
        place_name="Old place",
        city="Old city",
        address="Old address",
        raw_location_data={"old": True},
        location_source=LocationSource.SOURCE,
        selected_location_components=components,
        location_text="My editorial city",
        location_selection_edited=True,
        caption="My caption",
    )

    resolved = resolve_photo_metadata(
        photo,
        policy(location="none"),
    )

    assert resolved.place_name is None
    assert resolved.city is None
    assert resolved.address is None
    assert resolved.raw_location_data is None
    assert resolved.location_source == LocationSource.UNKNOWN

    assert resolved.source_location_data == source_candidate
    assert resolved.geocoded_location_data == geocoded_candidate

    assert resolved.selected_location_components == components
    assert resolved.location_text == "My editorial city"
    assert resolved.location_selection_edited is True
    assert resolved.caption == "My caption"
