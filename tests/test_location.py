from photoalbum.models import Location


def test_location_stores_coordinates():
    location = Location(
        latitude=46.5,
        longitude=-1.25,
    )

    assert location.latitude == 46.5
    assert location.longitude == -1.25


def test_location_can_store_geocoding_information():
    location = Location(
        latitude=46.5,
        longitude=-1.25,
        place_name="Example Place",
        city="Example City",
        address="1 Example Street",
    )

    assert location.place_name == "Example Place"
    assert location.city == "Example City"
    assert location.address == "1 Example Street"

