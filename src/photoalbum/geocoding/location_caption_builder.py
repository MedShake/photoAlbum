from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .location_candidate import LocationCandidate
from .location_candidate_extractor import LocationCandidateExtractor
from .location_candidate_selector import LocationCandidateSelector
from .location_caption_formatter import LocationCaptionFormatter


@dataclass(frozen=True)
class LocationCaptionResult:
    caption: str
    candidates: tuple[LocationCandidate, ...]
    selected: tuple[LocationCandidate, ...]


class LocationCaptionBuilder:
    """
    Build the automatic album caption from raw reverse-geocoding data.

    The result also exposes all available candidates and the automatically
    selected candidates so that a UI can later present and override the
    automatic choice.
    """

    def __init__(
        self,
        extractor: LocationCandidateExtractor | None = None,
        selector: LocationCandidateSelector | None = None,
        formatter: LocationCaptionFormatter | None = None,
    ) -> None:
        self._extractor = extractor or LocationCandidateExtractor()
        self._selector = selector or LocationCandidateSelector()
        self._formatter = formatter or LocationCaptionFormatter()

    def build(
        self,
        raw_data: Mapping[str, Any] | None,
    ) -> LocationCaptionResult:
        candidates = self._extractor.extract(raw_data)
        selected = self._selector.select(candidates)
        caption = self._formatter.format(selected)

        return LocationCaptionResult(
            caption=caption,
            candidates=tuple(candidates),
            selected=tuple(selected),
        )
