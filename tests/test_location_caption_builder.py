from photoalbum.geocoding.location_caption_builder import (
    LocationCaptionBuilder,
)


def test_empty_data_returns_empty_result():
    builder = LocationCaptionBuilder()

    result = builder.build(None)

    assert result.caption == ""
    assert result.candidates == ()
    assert result.selected == ()


def test_builder_creates_short_caption():
    builder = LocationCaptionBuilder()

    result = builder.build(
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

    assert result.caption == (
        "Château de Chenonceau, Chenonceaux"
    )


def test_result_keeps_all_available_candidates():
    builder = LocationCaptionBuilder()

    result = builder.build(
        {
            "address": {
                "tourism": "Château de Chenonceau",
                "road": "Rue du Château",
                "village": "Chenonceaux",
                "country": "France",
            }
        }
    )

    assert [(c.key, c.value) for c in result.candidates] == [
        ("tourism", "Château de Chenonceau"),
        ("road", "Rue du Château"),
        ("village", "Chenonceaux"),
        ("country", "France"),
    ]


def test_result_exposes_automatic_selection():
    builder = LocationCaptionBuilder()

    result = builder.build(
        {
            "address": {
                "tourism": "Sacré-Cœur",
                "neighbourhood": "Montmartre",
                "city": "Paris",
                "country": "France",
            }
        }
    )

    assert [(c.key, c.value) for c in result.selected] == [
        ("tourism", "Sacré-Cœur"),
        ("neighbourhood", "Montmartre"),
        ("city", "Paris"),
    ]

    assert result.caption == "Sacré-Cœur, Montmartre, Paris"


def test_unknown_fields_remain_available_but_are_not_selected():
    builder = LocationCaptionBuilder()

    result = builder.build(
        {
            "address": {
                "future_osm_type": "Interesting value",
                "town": "Example Town",
            }
        }
    )

    assert [(c.key, c.value) for c in result.candidates] == [
        ("future_osm_type", "Interesting value"),
        ("town", "Example Town"),
    ]

    assert [(c.key, c.value) for c in result.selected] == [
        ("town", "Example Town"),
    ]

    assert result.caption == "Example Town"


def test_postal_fields_remain_available_for_manual_selection():
    builder = LocationCaptionBuilder()

    result = builder.build(
        {
            "address": {
                "house_number": "12",
                "road": "Rue Example",
                "postcode": "44000",
                "city": "Nantes",
            }
        }
    )

    assert [c.key for c in result.candidates] == [
        "house_number",
        "road",
        "postcode",
        "city",
    ]

    assert [c.key for c in result.selected] == [
        "road",
        "city",
    ]

    assert result.caption == "Rue Example, Nantes"
