from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF

from photoalbum.templates.msb.geographic_map.geography import (
    longitude_near_reference,
    minimal_longitude_interval,
    load_countries,
    map_bounds_for_points,
)
from photoalbum.templates.msb.geographic_map.painter import (
    PROJECTION_WEB_MERCATOR,
    _map_rect,
    _project,
    _projected_bounds,
)


def test_longitude_just_left_of_extent_stays_local():
    assert longitude_near_reference(
        178.28018,
        179.65,
    ) == pytest.approx(
        178.28018
    )


def test_antimeridian_longitude_moves_adjacent():
    assert longitude_near_reference(
        -179.5,
        179.65,
    ) == pytest.approx(
        180.5
    )


def test_longitude_left_of_extent_stays_local():
    assert longitude_near_reference(
        177.0,
        179.65,
    ) == pytest.approx(
        177.0
    )


def test_positive_world_copy_returns_nearest_copy():
    assert longitude_near_reference(
        538.0,
        179.65,
    ) == pytest.approx(
        178.0
    )


def test_minimal_interval_normal_region_stays_local():
    minimum, maximum = minimal_longitude_interval(
        (
            116.4074,
            121.4737,
            108.9398,
        )
    )

    assert minimum == pytest.approx(
        108.9398
    )
    assert maximum == pytest.approx(
        121.4737
    )


def test_real_fiji_ring_does_not_jump_world_copy():
    fake_points = (
        (179.50, -17.70),
        (-179.50, -17.40),
        (178.80, -18.10),
    )

    bounds = map_bounds_for_points(
        fake_points
    )

    target = QRectF(
        40.0,
        40.0,
        1320.0,
        820.0,
    )

    projection = PROJECTION_WEB_MERCATOR

    map_rect = _map_rect(
        bounds,
        target,
        projection,
    )

    projected_bounds = _projected_bounds(
        bounds,
        projection,
    )

    fiji = next(
        country
        for country in load_countries()
        if country.name == "Fiji"
    )

    ring = fiji.rings[1]

    projected = [
        _project(
            longitude,
            latitude,
            bounds,
            map_rect,
            projection,
            projected_bounds,
        )
        for longitude, latitude in ring
    ]

    xs = [
        point.x()
        for point in projected
    ]

    # Regression for the observed ~152000 px failure.
    assert max(xs) < (
        map_rect.right()
        + map_rect.width()
    )

    assert min(xs) > (
        map_rect.left()
        - map_rect.width()
    )


def test_fiji_fake_bounds_remain_local():
    bounds = map_bounds_for_points(
        (
            (179.50, -17.70),
            (-179.50, -17.40),
            (178.80, -18.10),
        )
    )

    assert bounds.longitude_span < 10.0

    assert bounds.minimum_longitude == pytest.approx(
        178.3
    )

    assert bounds.maximum_longitude == pytest.approx(
        181.0
    )
