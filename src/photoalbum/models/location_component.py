from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LocationComponent:
    """
    Geographic component selected to describe where a photo was taken.

    The key and value are preserved from the reverse-geocoding response.
    """

    key: str
    value: str
