from photoalbum.geocoding.location_candidate import (
    LocationCandidate,
    LocationCandidatePriority,
)
from photoalbum.geocoding.location_candidate_selector import (
    LocationCandidateSelector,
)


def candidate(
    key: str,
    value: str,
    priority: LocationCandidatePriority,
) -> LocationCandidate:
    return LocationCandidate(
        key=key,
        value=value,
        priority=priority,
    )


def test_named_place_and_locality_are_selected():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "tourism",
            "Château de Chenonceau",
            LocationCandidatePriority.PLACE,
        ),
        candidate(
            "road",
            "Rue du Château",
            LocationCandidatePriority.ROAD,
        ),
        candidate(
            "village",
            "Chenonceaux",
            LocationCandidatePriority.LOCALITY,
        ),
        candidate(
            "county",
            "Indre-et-Loire",
            LocationCandidatePriority.ADMINISTRATIVE,
        ),
        candidate(
            "country",
            "France",
            LocationCandidatePriority.COUNTRY,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("tourism", "Château de Chenonceau"),
        ("village", "Chenonceaux"),
    ]


def test_local_context_is_kept_between_place_and_city():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "tourism",
            "Sacré-Cœur",
            LocationCandidatePriority.PLACE,
        ),
        candidate(
            "neighbourhood",
            "Montmartre",
            LocationCandidatePriority.LOCAL_CONTEXT,
        ),
        candidate(
            "city",
            "Paris",
            LocationCandidatePriority.LOCALITY,
        ),
        candidate(
            "country",
            "France",
            LocationCandidatePriority.COUNTRY,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("tourism", "Sacré-Cœur"),
        ("neighbourhood", "Montmartre"),
        ("city", "Paris"),
    ]


def test_road_is_used_when_named_place_is_missing():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "road",
            "Rue du Gros-Horloge",
            LocationCandidatePriority.ROAD,
        ),
        candidate(
            "city",
            "Rouen",
            LocationCandidatePriority.LOCALITY,
        ),
        candidate(
            "state",
            "Normandie",
            LocationCandidatePriority.ADMINISTRATIVE,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("road", "Rue du Gros-Horloge"),
        ("city", "Rouen"),
    ]


def test_locality_alone_is_enough():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "village",
            "Gordes",
            LocationCandidatePriority.LOCALITY,
        ),
        candidate(
            "county",
            "Vaucluse",
            LocationCandidatePriority.ADMINISTRATIVE,
        ),
        candidate(
            "state",
            "Provence-Alpes-Côte d'Azur",
            LocationCandidatePriority.ADMINISTRATIVE,
        ),
        candidate(
            "country",
            "France",
            LocationCandidatePriority.COUNTRY,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("village", "Gordes"),
    ]


def test_administrative_value_is_fallback_without_locality():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "county",
            "Vaucluse",
            LocationCandidatePriority.ADMINISTRATIVE,
        ),
        candidate(
            "state",
            "Provence-Alpes-Côte d'Azur",
            LocationCandidatePriority.ADMINISTRATIVE,
        ),
        candidate(
            "country",
            "France",
            LocationCandidatePriority.COUNTRY,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("county", "Vaucluse"),
    ]


def test_country_is_last_resort():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "postcode",
            "37150",
            LocationCandidatePriority.POSTAL,
        ),
        candidate(
            "country",
            "France",
            LocationCandidatePriority.COUNTRY,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("country", "France"),
    ]


def test_postal_information_is_not_selected():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "house_number",
            "12",
            LocationCandidatePriority.POSTAL,
        ),
        candidate(
            "postcode",
            "76000",
            LocationCandidatePriority.POSTAL,
        ),
        candidate(
            "city",
            "Rouen",
            LocationCandidatePriority.LOCALITY,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("city", "Rouen"),
    ]


def test_duplicate_values_are_not_selected_twice():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "tourism",
            "Mont-Saint-Michel",
            LocationCandidatePriority.PLACE,
        ),
        candidate(
            "village",
            "Mont-Saint-Michel",
            LocationCandidatePriority.LOCALITY,
        ),
        candidate(
            "country",
            "France",
            LocationCandidatePriority.COUNTRY,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("tourism", "Mont-Saint-Michel"),
    ]


def test_duplicate_detection_is_case_insensitive():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "tourism",
            "MONTMARTRE",
            LocationCandidatePriority.PLACE,
        ),
        candidate(
            "neighbourhood",
            "Montmartre",
            LocationCandidatePriority.LOCAL_CONTEXT,
        ),
        candidate(
            "city",
            "Paris",
            LocationCandidatePriority.LOCALITY,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("tourism", "MONTMARTRE"),
        ("city", "Paris"),
    ]


def test_unknown_candidates_are_not_selected_automatically():
    selector = LocationCandidateSelector()

    candidates = [
        candidate(
            "some_future_nominatim_type",
            "Something useful",
            LocationCandidatePriority.OTHER,
        ),
        candidate(
            "town",
            "Example Town",
            LocationCandidatePriority.LOCALITY,
        ),
    ]

    selected = selector.select(candidates)

    assert [(c.key, c.value) for c in selected] == [
        ("town", "Example Town"),
    ]
