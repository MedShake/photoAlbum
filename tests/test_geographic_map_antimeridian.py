from __future__ import annotations

import pytest

from photoalbum.templates.msb.geographic_map.geography import (
    map_bounds_for_points,
)


def _longitude_inside_bounds(
    longitude: float,
    minimum: float,
    maximum: float,
) -> bool:
    """
    Test all equivalent representations of a longitude.

    Example:
        -179 == 181 == 541 ...
    """
    for offset in (
        -720.0,
        -360.0,
        0.0,
        360.0,
        720.0,
    ):
        value = longitude + offset

        if minimum <= value <= maximum:
            return True

    return False


def test_antimeridian_uses_short_arc():
    bounds = map_bounds_for_points(
        (
            (179.0, 0.0),
            (-179.0, 0.0),
        )
    )

    # Padding is allowed, but this must remain
    # a local Pacific extent, not ~358 degrees.
    assert 0.0 < bounds.longitude_span < 20.0


def test_antimeridian_contains_both_points():
    bounds = map_bounds_for_points(
        (
            (179.0, 0.0),
            (-179.0, 0.0),
        )
    )

    assert _longitude_inside_bounds(
        179.0,
        bounds.minimum_longitude,
        bounds.maximum_longitude,
    )

    assert _longitude_inside_bounds(
        -179.0,
        bounds.minimum_longitude,
        bounds.maximum_longitude,
    )


def test_fiji_style_extent_is_local():
    bounds = map_bounds_for_points(
        (
            (178.1, -17.7),
            (-179.8, -16.5),
            (179.4, -18.1),
        )
    )

    assert bounds.longitude_span < 20.0

    for longitude in (
        178.1,
        -179.8,
        179.4,
    ):
        assert _longitude_inside_bounds(
            longitude,
            bounds.minimum_longitude,
            bounds.maximum_longitude,
        )


def test_greenwich_extent_stays_conventional():
    bounds = map_bounds_for_points(
        (
            (-1.5536, 47.2184),
            (2.3522, 48.8566),
        )
    )

    assert bounds.minimum_longitude < 0.0
    assert bounds.maximum_longitude > 0.0
    assert bounds.longitude_span < 20.0


def test_china_extent_does_not_wrap():
    bounds = map_bounds_for_points(
        (
            (116.4074, 39.9042),
            (121.4737, 31.2304),
            (108.9398, 34.3416),
        )
    )

    # The map deliberately includes the containing
    # Natural Earth country component, not only the photos.
    assert bounds.longitude_span < 100.0

    for longitude in (
        116.4074,
        121.4737,
        108.9398,
    ):
        assert _longitude_inside_bounds(
            longitude,
            bounds.minimum_longitude,
            bounds.maximum_longitude,
        )


def test_equivalent_longitudes_are_recognised():
    assert _longitude_inside_bounds(
        -179.0,
        178.0,
        182.0,
    )

    assert _longitude_inside_bounds(
        179.0,
        178.0,
        182.0,
    )

    assert not _longitude_inside_bounds(
        0.0,
        178.0,
        182.0,
    )


def test_minimal_longitude_interval_crosses_antimeridian():
    from photoalbum.templates.msb.geographic_map.geography import (
        minimal_longitude_interval,
    )

    minimum, maximum = minimal_longitude_interval(
        (179.0, -179.0)
    )

    assert maximum - minimum == pytest.approx(2.0)

    assert minimum == pytest.approx(179.0)
    assert maximum == pytest.approx(181.0)


def test_minimal_longitude_interval_normal_case():
    from photoalbum.templates.msb.geographic_map.geography import (
        minimal_longitude_interval,
    )

    minimum, maximum = minimal_longitude_interval(
        (-10.0, 2.0, 20.0)
    )

    assert minimum == pytest.approx(-10.0)
    assert maximum == pytest.approx(20.0)


def test_unwrap_longitude_around_pacific():
    from photoalbum.templates.msb.geographic_map.geography import (
        unwrap_longitude,
    )

    assert unwrap_longitude(
        -179.0,
        178.0,
    ) == pytest.approx(181.0)
