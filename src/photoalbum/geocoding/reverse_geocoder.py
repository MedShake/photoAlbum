from __future__ import annotations

from typing import Protocol

from photoalbum.models import Location


class ReverseGeocoder(Protocol):
    def reverse(
        self,
        latitude: float,
        longitude: float,
        language: str | None = None,
    ) -> Location | None:
        """
        Resolve GPS coordinates into geographic information.

        Returns None when no suitable location can be resolved.
        """
        ...

