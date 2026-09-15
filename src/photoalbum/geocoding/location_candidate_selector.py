from __future__ import annotations

from collections.abc import Iterable

from .location_candidate import (
    LocationCandidate,
    LocationCandidatePriority,
)


class LocationCandidateSelector:
    """
    Select a short, useful set of location candidates for a photo caption.

    Candidates keep their original Nominatim keys. This class only decides
    which values are useful enough to select automatically.
    """

    def select(
        self,
        candidates: Iterable[LocationCandidate],
    ) -> list[LocationCandidate]:
        candidates = list(candidates)

        selected: list[LocationCandidate] = []

        place = self._first_with_priority(
            candidates,
            LocationCandidatePriority.PLACE,
        )

        road = self._first_with_priority(
            candidates,
            LocationCandidatePriority.ROAD,
        )

        local_context = self._first_with_priority(
            candidates,
            LocationCandidatePriority.LOCAL_CONTEXT,
        )

        locality = self._first_with_priority(
            candidates,
            LocationCandidatePriority.LOCALITY,
        )

        administrative = self._first_with_priority(
            candidates,
            LocationCandidatePriority.ADMINISTRATIVE,
        )

        country = self._first_with_priority(
            candidates,
            LocationCandidatePriority.COUNTRY,
        )

        # A named place is preferable to a road.
        if place is not None:
            self._append_unique(selected, place)
        elif road is not None:
            self._append_unique(selected, road)

        # A neighbourhood/suburb can be meaningful in a photo album,
        # especially in large cities.
        if local_context is not None:
            self._append_unique(selected, local_context)

        if locality is not None:
            self._append_unique(selected, locality)

        # Administrative information is primarily a fallback when no
        # locality could be identified.
        if locality is None and administrative is not None:
            self._append_unique(selected, administrative)

        # Country is a last-resort fallback. It is not automatically added
        # to an otherwise useful caption.
        if not selected and country is not None:
            self._append_unique(selected, country)

        return selected

    @staticmethod
    def _first_with_priority(
        candidates: list[LocationCandidate],
        priority: LocationCandidatePriority,
    ) -> LocationCandidate | None:
        for candidate in candidates:
            if candidate.priority == priority:
                return candidate

        return None

    @staticmethod
    def _append_unique(
        selected: list[LocationCandidate],
        candidate: LocationCandidate,
    ) -> None:
        normalized_value = candidate.value.casefold()

        if any(
            existing.value.casefold() == normalized_value
            for existing in selected
        ):
            return

        selected.append(candidate)
