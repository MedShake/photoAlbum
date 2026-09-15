from __future__ import annotations

from collections.abc import Iterable

from .location_candidate import LocationCandidate


class LocationCaptionFormatter:
    """
    Format already-selected location candidates as a short album caption.

    This class deliberately knows nothing about Nominatim priorities or
    automatic selection rules.
    """

    def __init__(self, separator: str = ", ") -> None:
        self._separator = separator

    def format(
        self,
        candidates: Iterable[LocationCandidate],
    ) -> str:
        values: list[str] = []

        for candidate in candidates:
            value = candidate.value.strip()

            if not value:
                continue

            if any(
                existing.casefold() == value.casefold()
                for existing in values
            ):
                continue

            values.append(value)

        return self._separator.join(values)
