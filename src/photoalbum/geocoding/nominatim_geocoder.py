from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from photoalbum.models import Location

from .nominatim_parser import NominatimParser
from .rate_limiter import RateLimiter


class GeocodingError(RuntimeError):
    """Raised when a reverse-geocoding request cannot be completed."""


class NominatimGeocoder:
    DEFAULT_ENDPOINT = "https://nominatim.openstreetmap.org/reverse"

    def __init__(
        self,
        user_agent: str,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = 10.0,
        rate_limiter: RateLimiter | None = None,
        parser: NominatimParser | None = None,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("User-Agent cannot be empty.")

        if timeout_seconds <= 0:
            raise ValueError("Timeout must be greater than zero.")

        self._user_agent = user_agent
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._rate_limiter = rate_limiter or RateLimiter(1.0)
        self._parser = parser or NominatimParser()
        self._opener = opener

    def reverse(
        self,
        latitude: float,
        longitude: float,
        language: str | None = None,
    ) -> Location | None:
        self._validate_coordinates(
            latitude,
            longitude,
        )

        parameters = {
            "format": "jsonv2",
            "lat": str(latitude),
            "lon": str(longitude),
            "addressdetails": "1",
        }

        if language:
            parameters["accept-language"] = language

        url = f"{self._endpoint}?{urlencode(parameters)}"

        request = Request(
            url,
            headers={
                "User-Agent": self._user_agent,
                "Accept": "application/json",
            },
        )

        self._rate_limiter.wait()

        try:
            with self._opener(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                payload = response.read()

        except HTTPError as exc:
            if exc.code == 404:
                return None

            raise GeocodingError(
                f"Nominatim returned HTTP {exc.code}."
            ) from exc

        except URLError as exc:
            raise GeocodingError(
                f"Unable to contact Nominatim: {exc.reason}"
            ) from exc

        except TimeoutError as exc:
            raise GeocodingError(
                "Nominatim request timed out."
            ) from exc

        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GeocodingError(
                "Nominatim returned an invalid JSON response."
            ) from exc

        if not isinstance(data, dict):
            raise GeocodingError(
                "Nominatim returned an unexpected response."
            )

        if "error" in data:
            return None

        return self._parser.parse(
            data,
            latitude=latitude,
            longitude=longitude,
        )

    @staticmethod
    def _validate_coordinates(
        latitude: float,
        longitude: float,
    ) -> None:
        if not -90.0 <= latitude <= 90.0:
            raise ValueError(
                f"Invalid latitude: {latitude}"
            )

        if not -180.0 <= longitude <= 180.0:
            raise ValueError(
                f"Invalid longitude: {longitude}"
            )

