from photoalbum.geocoding.location_candidate import (
    LocationCandidate,
    LocationCandidatePriority,
)
from photoalbum.geocoding.location_caption_formatter import (
    LocationCaptionFormatter,
)


def candidate(
    key: str,
    value: str,
) -> LocationCandidate:
    return LocationCandidate(
        key=key,
        value=value,
        priority=LocationCandidatePriority.OTHER,
    )


def test_empty_selection_returns_empty_caption():
    formatter = LocationCaptionFormatter()

    assert formatter.format([]) == ""


def test_single_candidate_returns_its_value():
    formatter = LocationCaptionFormatter()

    result = formatter.format(
        [
            candidate(
                "village",
                "Gordes",
            )
        ]
    )

    assert result == "Gordes"


def test_selected_candidates_are_joined_in_order():
    formatter = LocationCaptionFormatter()

    result = formatter.format(
        [
            candidate(
                "tourism",
                "Château de Chenonceau",
            ),
            candidate(
                "village",
                "Chenonceaux",
            ),
        ]
    )

    assert result == (
        "Château de Chenonceau, Chenonceaux"
    )


def test_three_candidates_are_supported():
    formatter = LocationCaptionFormatter()

    result = formatter.format(
        [
            candidate(
                "tourism",
                "Sacré-Cœur",
            ),
            candidate(
                "neighbourhood",
                "Montmartre",
            ),
            candidate(
                "city",
                "Paris",
            ),
        ]
    )

    assert result == "Sacré-Cœur, Montmartre, Paris"


def test_duplicate_values_are_not_rendered_twice():
    formatter = LocationCaptionFormatter()

    result = formatter.format(
        [
            candidate(
                "tourism",
                "Mont-Saint-Michel",
            ),
            candidate(
                "village",
                "Mont-Saint-Michel",
            ),
        ]
    )

    assert result == "Mont-Saint-Michel"


def test_duplicate_detection_is_case_insensitive():
    formatter = LocationCaptionFormatter()

    result = formatter.format(
        [
            candidate(
                "tourism",
                "MONTMARTRE",
            ),
            candidate(
                "neighbourhood",
                "Montmartre",
            ),
            candidate(
                "city",
                "Paris",
            ),
        ]
    )

    assert result == "MONTMARTRE, Paris"


def test_values_are_trimmed():
    formatter = LocationCaptionFormatter()

    result = formatter.format(
        [
            candidate(
                "road",
                "  Rue Example  ",
            ),
            candidate(
                "city",
                " Nantes ",
            ),
        ]
    )

    assert result == "Rue Example, Nantes"


def test_custom_separator_can_be_used():
    formatter = LocationCaptionFormatter(
        separator=" · ",
    )

    result = formatter.format(
        [
            candidate(
                "tourism",
                "Musée Example",
            ),
            candidate(
                "city",
                "Paris",
            ),
        ]
    )

    assert result == "Musée Example · Paris"
