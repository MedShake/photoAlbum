from photoalbum.geocoding import NominatimParser


def test_empty_response_returns_none():
    parser = NominatimParser()

    result = parser.parse(
        {},
        latitude=46.67,
        longitude=-1.57,
    )

    assert result is None


def test_parser_uses_city():
    parser = NominatimParser()

    result = parser.parse(
        {
            "display_name": (
                "1 Rue Example, Nantes, Loire-Atlantique, France"
            ),
            "address": {
                "house_number": "1",
                "road": "Rue Example",
                "city": "Nantes",
                "country": "France",
            },
        },
        latitude=47.2184,
        longitude=-1.5536,
    )

    assert result is not None
    assert result.city == "Nantes"
    assert result.address == (
        "1 Rue Example, Nantes, Loire-Atlantique, France"
    )


def test_parser_uses_town_when_city_is_missing():
    parser = NominatimParser()

    result = parser.parse(
        {
            "display_name": "Example address",
            "address": {
                "town": "Example Town",
            },
        },
        latitude=46.67,
        longitude=-1.57,
    )

    assert result is not None
    assert result.city == "Example Town"


def test_parser_uses_village_when_city_and_town_are_missing():
    parser = NominatimParser()

    result = parser.parse(
        {
            "display_name": "Example address",
            "address": {
                "village": "Example Village",
            },
        },
        latitude=46.67,
        longitude=-1.57,
    )

    assert result is not None
    assert result.city == "Example Village"


def test_city_has_priority_over_other_locality_types():
    parser = NominatimParser()

    result = parser.parse(
        {
            "address": {
                "city": "Main City",
                "town": "Secondary Town",
                "village": "Secondary Village",
            },
        },
        latitude=46.67,
        longitude=-1.57,
    )

    assert result is not None
    assert result.city == "Main City"


def test_parser_extracts_named_place():
    parser = NominatimParser()

    result = parser.parse(
        {
            "display_name": "Example Museum, Example City",
            "address": {
                "tourism": "Example Museum",
                "city": "Example City",
            },
        },
        latitude=46.67,
        longitude=-1.57,
    )

    assert result is not None
    assert result.place_name == "Example Museum"


def test_parser_keeps_requested_coordinates():
    parser = NominatimParser()

    result = parser.parse(
        {
            "display_name": "Example address",
            "address": {
                "city": "Example City",
            },
        },
        latitude=46.123456,
        longitude=-1.654321,
    )

    assert result is not None
    assert result.latitude == 46.123456
    assert result.longitude == -1.654321


def test_missing_address_information_is_allowed():
    parser = NominatimParser()

    result = parser.parse(
        {
            "display_name": "Somewhere",
        },
        latitude=46.67,
        longitude=-1.57,
    )

    assert result is not None
    assert result.city is None
    assert result.place_name is None
    assert result.address == "Somewhere"

