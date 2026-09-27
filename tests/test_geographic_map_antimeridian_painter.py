from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF

from photoalbum.templates.msb.geographic_map.geography import (
    GeographicBounds,
    continuous_ring,
    ring_bounds,
)
from photoalbum.templates.msb.geographic_map.painter import (
    PROJECTION_EQUAL_EARTH,
    PROJECTION_ROBINSON,
    PROJECTION_WEB_MERCATOR,
    _map_rect,
    _project,
    _visible_rings,
)

from photoalbum.templates.msb.geographic_map import painter as map_painter


PACIFIC_BOUNDS = GeographicBounds(
    minimum_longitude=178.0,
    minimum_latitude=-25.0,
    maximum_longitude=182.0,
    maximum_latitude=-10.0,
)

PROJECTIONS = (
    PROJECTION_WEB_MERCATOR,
    PROJECTION_EQUAL_EARTH,
    PROJECTION_ROBINSON,
)


@pytest.mark.parametrize(
    "projection",
    PROJECTIONS,
)
def test_antimeridian_points_project_close_together(
    projection,
):
    rect = _map_rect(
        PACIFIC_BOUNDS,
        QRectF(
            0.0,
            0.0,
            1000.0,
            600.0,
        ),
        projection,
    )

    east = _project(
        179.0,
        -17.0,
        PACIFIC_BOUNDS,
        rect,
        projection,
    )

    west = _project(
        -179.0,
        -17.0,
        PACIFIC_BOUNDS,
        rect,
        projection,
    )

    assert abs(
        east.x() - west.x()
    ) < rect.width()


@pytest.mark.parametrize(
    "projection",
    PROJECTIONS,
)
def test_antimeridian_points_stay_inside_map(
    projection,
):
    rect = _map_rect(
        PACIFIC_BOUNDS,
        QRectF(
            0.0,
            0.0,
            1000.0,
            600.0,
        ),
        projection,
    )

    for longitude in (
        179.0,
        -179.0,
    ):
        point = _project(
            longitude,
            -17.0,
            PACIFIC_BOUNDS,
            rect,
            projection,
        )

        assert (
            rect.left() - 1e-6
            <= point.x()
            <= rect.right() + 1e-6
        )

        assert (
            rect.top() - 1e-6
            <= point.y()
            <= rect.bottom() + 1e-6
        )


@pytest.fixture
def visible_rings(monkeypatch):
    def select(ring, bounds):
        ring = continuous_ring(ring)
        monkeypatch.setattr(
            map_painter, "country_components",
            lambda: ((None, ring, ring_bounds(ring)),),
        )
        return tuple(_visible_rings(bounds))
    return select


def test_ring_across_antimeridian_intersects_pacific_bounds(visible_rings):
    ring = (
        (179.0, -20.0),
        (-179.0, -20.0),
        (-179.0, -15.0),
        (179.0, -15.0),
        (179.0, -20.0),
    )

    assert visible_rings(
        ring,
        PACIFIC_BOUNDS,
    )


def test_greenwich_ring_does_not_intersect_pacific_bounds(visible_rings):
    ring = (
        (-5.0, -20.0),
        (5.0, -20.0),
        (5.0, -15.0),
        (-5.0, -15.0),
        (-5.0, -20.0),
    )

    assert not visible_rings(
        ring,
        PACIFIC_BOUNDS,
    )


def test_normal_european_bounds_still_work(visible_rings):
    bounds = GeographicBounds(
        minimum_longitude=-10.0,
        minimum_latitude=40.0,
        maximum_longitude=30.0,
        maximum_latitude=70.0,
    )

    ring = (
        (-5.0, 45.0),
        (10.0, 45.0),
        (10.0, 55.0),
        (-5.0, 55.0),
        (-5.0, 45.0),
    )

    assert visible_rings(
        ring,
        bounds,
    )
