from __future__ import annotations

from collections.abc import Iterable

from .location_candidate import (
    LocationCandidate,
    LocationCandidatePriority,
)


class LocationCandidateSelector:
    """
    Select a short, useful set of location candidates for a photo caption.

    A caption can combine several geographic levels. In particular, a small
    locality such as a hamlet is useful as local context but must never be
    selected on its own.
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

        small_locality = self._first_with_priority(
            candidates,
            LocationCandidatePriority.SMALL_LOCALITY,
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

        # Neighbourhoods, quarters and suburbs provide useful local context.
        if local_context is not None:
            self._append_unique(selected, local_context)

        # A hamlet or isolated dwelling is meaningful only when accompanied
        # by a more significant locality. It must never stand alone.
        if small_locality is not None and locality is not None:
            self._append_unique(selected, small_locality)

        if locality is not None:
            self._append_unique(selected, locality)

        # Administrative information is primarily a fallback when no
        # locality could be identified. A small locality does not count as
        # a sufficient locality for this purpose.
        if locality is None and administrative is not None:
            self._append_unique(selected, administrative)

        # Country is the final fallback.
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
