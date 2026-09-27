from __future__ import annotations

import pytest

from photoalbum.templates.msb.geographic_map.geography import continuous_ring


def test_antimeridian_ring_is_continuous():
    ring = (
        (179.0, -18.0),
        (-179.0, -18.0),
        (-178.0, -17.0),
        (179.0, -17.0),
        (179.0, -18.0),
    )

    result = continuous_ring(ring)

    longitudes = [
        longitude
        for longitude, _latitude in result
    ]

    assert longitudes == pytest.approx(
        (
            179.0,
            181.0,
            182.0,
            179.0,
            179.0,
        )
    )


def test_greenwich_ring_remains_near_greenwich():
    ring = (
        (-5.0, -20.0),
        (5.0, -20.0),
        (5.0, -15.0),
        (-5.0, -15.0),
        (-5.0, -20.0),
    )

    result = continuous_ring(ring)

    longitudes = [
        longitude
        for longitude, _latitude in result
    ]

    # Unwrapping connected geometry must preserve the Greenwich ring.
    assert result == ring
    differences = [
        abs(current - previous)
        for previous, current in zip(
            longitudes,
            longitudes[1:],
        )
    ]

    assert max(differences) < 180.0


def test_every_segment_stays_continuous():
    ring = (
        (178.0, -18.0),
        (179.5, -18.0),
        (-179.8, -17.5),
        (-178.0, -17.0),
        (179.0, -17.0),
        (178.0, -18.0),
    )

    result = continuous_ring(ring)

    for previous, current in zip(
        result,
        result[1:],
    ):
        assert abs(
            current[0] - previous[0]
        ) <= 180.0


def test_closed_ring_closes_in_same_world_copy():
    ring = (
        (179.0, -18.0),
        (-179.0, -18.0),
        (-179.0, -17.0),
        (179.0, -17.0),
        (179.0, -18.0),
    )

    result = continuous_ring(ring)

    assert result[0][0] == pytest.approx(
        result[-1][0]
    )

    assert result[0][1] == pytest.approx(
        result[-1][1]
    )
