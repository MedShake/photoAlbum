import json
from urllib.error import HTTPError, URLError

import pytest

from photoalbum.geocoding import (
    GeocodingError,
    NominatimGeocoder,
)


class FakeResponse:
    def __init__(self, data):
        self._payload = json.dumps(data).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


class FakeRateLimiter:
    def __init__(self):
        self.calls = 0

    def wait(self):
        self.calls += 1


def test_reverse_geocoding_builds_location():
    def opener(request, timeout):
        return FakeResponse(
            {
                "display_name": "Example Place, Nantes, France",
                "address": {
                    "tourism": "Example Place",
                    "city": "Nantes",
                    "country": "France",
                },
            }
        )

    geocoder = NominatimGeocoder(
        "PhotoAlbum/0.1",
        opener=opener,
    )

    result = geocoder.reverse(
        47.2184,
        -1.5536,
    )

    assert result is not None
    assert result.city == "Nantes"
    assert result.place_name == "Example Place"


def test_user_agent_is_sent():
    captured_request = None

    def opener(request, timeout):
        nonlocal captured_request
        captured_request = request

        return FakeResponse(
            {
                "display_name": "Example",
                "address": {},
            }
        )

    geocoder = NominatimGeocoder(
        "PhotoAlbum/0.1",
        opener=opener,
    )

    geocoder.reverse(
        46.67,
        -1.57,
    )

    assert captured_request is not None
    assert (
        captured_request.get_header("User-agent")
        == "PhotoAlbum/0.1"
    )


def test_language_is_added_to_query():
    captured_url = None

    def opener(request, timeout):
        nonlocal captured_url
        captured_url = request.full_url

        return FakeResponse(
            {
                "display_name": "Example",
                "address": {},
            }
        )

    geocoder = NominatimGeocoder(
        "PhotoAlbum/0.1",
        opener=opener,
    )

    geocoder.reverse(
        46.67,
        -1.57,
        language="fr",
    )

    assert captured_url is not None
    assert "accept-language=fr" in captured_url


def test_rate_limiter_is_used():
    limiter = FakeRateLimiter()

    def opener(request, timeout):
        return FakeResponse(
            {
                "display_name": "Example",
                "address": {},
            }
        )

    geocoder = NominatimGeocoder(
        "PhotoAlbum/0.1",
        opener=opener,
        rate_limiter=limiter,
    )

    geocoder.reverse(
        46.67,
        -1.57,
    )

    assert limiter.calls == 1


def test_nominatim_error_response_returns_none():
    def opener(request, timeout):
        return FakeResponse(
            {
                "error": "Unable to geocode",
            }
        )

    geocoder = NominatimGeocoder(
        "PhotoAlbum/0.1",
        opener=opener,
    )

    result = geocoder.reverse(
        46.67,
        -1.57,
    )

    assert result is None


def test_http_404_returns_none():
    def opener(request, timeout):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            None,
        )

    geocoder = NominatimGeocoder(
        "PhotoAlbum/0.1",
        opener=opener,
    )

    assert geocoder.reverse(46.67, -1.57) is None


def test_network_error_raises_geocoding_error():
    def opener(request, timeout):
        raise URLError("Network unavailable")

    geocoder = NominatimGeocoder(
        "PhotoAlbum/0.1",
        opener=opener,
    )

    with pytest.raises(
        GeocodingError,
        match="Unable to contact",
    ):
        geocoder.reverse(
            46.67,
            -1.57,
        )


def test_invalid_json_raises_geocoding_error():
    class InvalidResponse:
        def read(self):
            return b"not-json"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def opener(request, timeout):
        return InvalidResponse()

    geocoder = NominatimGeocoder(
        "PhotoAlbum/0.1",
        opener=opener,
    )

    with pytest.raises(
        GeocodingError,
        match="invalid JSON",
    ):
        geocoder.reverse(
            46.67,
            -1.57,
        )


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (91.0, 0.0),
        (-91.0, 0.0),
        (0.0, 181.0),
        (0.0, -181.0),
    ],
)
def test_invalid_coordinates_are_rejected(
    latitude,
    longitude,
):
    geocoder = NominatimGeocoder(
        "PhotoAlbum/0.1",
    )

    with pytest.raises(ValueError):
        geocoder.reverse(
            latitude,
            longitude,
        )


def test_empty_user_agent_is_rejected():
    with pytest.raises(ValueError):
        NominatimGeocoder("")


def test_invalid_timeout_is_rejected():
    with pytest.raises(ValueError):
        NominatimGeocoder(
            "PhotoAlbum/0.1",
            timeout_seconds=0,
        )

