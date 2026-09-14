import pytest

from photoalbum.geocoding import distance_in_meters


def test_same_coordinates_have_zero_distance():
    distance = distance_in_meters(
        46.6700,
        -1.5700,
        46.6700,
        -1.5700,
    )

    assert distance == 0.0


def test_distance_is_symmetric():
    first = distance_in_meters(
        46.6700,
        -1.5700,
        46.6710,
        -1.5710,
    )

    second = distance_in_meters(
        46.6710,
        -1.5710,
        46.6700,
        -1.5700,
    )

    assert first == pytest.approx(second)


def test_small_coordinate_difference_is_measured_in_meters():
    distance = distance_in_meters(
        46.670000,
        -1.570000,
        46.670036,
        -1.570000,
    )

    assert distance == pytest.approx(
        4.0,
        abs=0.2,
    )


def test_larger_coordinate_difference_exceeds_five_meters():
    distance = distance_in_meters(
        46.670000,
        -1.570000,
        46.670090,
        -1.570000,
    )

    assert distance > 5.0

