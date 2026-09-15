from photoalbum.geocoding.location_candidate import (
    LocationCandidatePriority,
)
from photoalbum.geocoding.location_candidate_extractor import (
    LocationCandidateExtractor,
)


def test_empty_data_returns_no_candidates():
    extractor = LocationCandidateExtractor()

    assert extractor.extract(None) == []
    assert extractor.extract({}) == []


def test_missing_address_returns_no_candidates():
    extractor = LocationCandidateExtractor()

    assert extractor.extract(
        {
            "display_name": "Somewhere",
        }
    ) == []


def test_original_nominatim_keys_are_preserved():
    extractor = LocationCandidateExtractor()

    candidates = extractor.extract(
        {
            "address": {
                "tourism": "Château de Chenonceau",
                "road": "Rue du Château",
                "village": "Chenonceaux",
                "county": "Indre-et-Loire",
                "state": "Centre-Val de Loire",
                "postcode": "37150",
                "country": "France",
            }
        }
    )

    assert [(c.key, c.value) for c in candidates] == [
        ("tourism", "Château de Chenonceau"),
        ("road", "Rue du Château"),
        ("village", "Chenonceaux"),
        ("county", "Indre-et-Loire"),
        ("state", "Centre-Val de Loire"),
        ("postcode", "37150"),
        ("country", "France"),
    ]


def test_candidates_are_classified_without_renaming_keys():
    extractor = LocationCandidateExtractor()

    candidates = extractor.extract(
        {
            "address": {
                "historic": "Château Example",
                "pedestrian": "Rue Example",
                "neighbourhood": "Vieux quartier",
                "town": "Example Town",
                "county": "Example County",
                "postcode": "12345",
                "country": "France",
            }
        }
    )

    priorities = {
        candidate.key: candidate.priority
        for candidate in candidates
    }

    assert priorities["historic"] == (
        LocationCandidatePriority.PLACE
    )
    assert priorities["pedestrian"] == (
        LocationCandidatePriority.ROAD
    )
    assert priorities["neighbourhood"] == (
        LocationCandidatePriority.LOCAL_CONTEXT
    )
    assert priorities["town"] == (
        LocationCandidatePriority.LOCALITY
    )
    assert priorities["county"] == (
        LocationCandidatePriority.ADMINISTRATIVE
    )
    assert priorities["postcode"] == (
        LocationCandidatePriority.POSTAL
    )
    assert priorities["country"] == (
        LocationCandidatePriority.COUNTRY
    )


def test_unknown_string_key_is_preserved():
    extractor = LocationCandidateExtractor()

    candidates = extractor.extract(
        {
            "address": {
                "some_future_nominatim_type": "Interesting place",
            }
        }
    )

    assert len(candidates) == 1
    assert candidates[0].key == "some_future_nominatim_type"
    assert candidates[0].value == "Interesting place"
    assert candidates[0].priority == (
        LocationCandidatePriority.OTHER
    )


def test_empty_and_non_string_values_are_ignored():
    extractor = LocationCandidateExtractor()

    candidates = extractor.extract(
        {
            "address": {
                "city": " Nantes ",
                "road": "   ",
                "postcode": None,
                "rank": 42,
            }
        }
    )

    assert len(candidates) == 1
    assert candidates[0].key == "city"
    assert candidates[0].value == "Nantes"


def test_local_context_variants_are_classified():
    extractor = LocationCandidateExtractor()

    candidates = extractor.extract(
        {
            "address": {
                "neighbourhood": "Centre",
                "quarter": "Vieux quartier",
                "suburb": "Faubourg",
                "borough": "Arrondissement",
                "city_district": "District",
            }
        }
    )

    assert all(
        candidate.priority
        == LocationCandidatePriority.LOCAL_CONTEXT
        for candidate in candidates
    )


def test_locality_variants_are_classified():
    extractor = LocationCandidateExtractor()

    candidates = extractor.extract(
        {
            "address": {
                "city": "City",
                "town": "Town",
                "village": "Village",
                "municipality": "Municipality",
                "hamlet": "Hamlet",
                "isolated_dwelling": "Isolated dwelling",
            }
        }
    )

    assert all(
        candidate.priority
        == LocationCandidatePriority.LOCALITY
        for candidate in candidates
    )


def test_administrative_variants_are_classified():
    extractor = LocationCandidateExtractor()

    candidates = extractor.extract(
        {
            "address": {
                "county": "County",
                "state_district": "State district",
                "state": "State",
                "region": "Region",
            }
        }
    )

    assert all(
        candidate.priority
        == LocationCandidatePriority.ADMINISTRATIVE
        for candidate in candidates
    )


def test_root_metadata_are_not_address_candidates():
    extractor = LocationCandidateExtractor()

    candidates = extractor.extract(
        {
            "name": "Château de Chenonceau",
            "category": "tourism",
            "type": "attraction",
            "addresstype": "tourism",
            "address": {
                "tourism": "Château de Chenonceau",
                "village": "Chenonceaux",
            },
        }
    )

    assert [(candidate.key, candidate.value) for candidate in candidates] == [
        ("tourism", "Château de Chenonceau"),
        ("village", "Chenonceaux"),
    ]
