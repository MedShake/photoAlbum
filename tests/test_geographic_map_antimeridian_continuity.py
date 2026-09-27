from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF

from photoalbum.templates.msb.geographic_map.geography import (
    GeographicBounds,
)
from photoalbum.templates.msb.geographic_map.painter import (
    PROJECTION_EQUAL_EARTH,
    PROJECTION_ROBINSON,
    PROJECTION_WEB_MERCATOR,
    _map_rect,
    _project,
)


PACIFIC_BOUNDS = GeographicBounds(
    minimum_longitude=177.0,
    minimum_latitude=-25.0,
    maximum_longitude=183.0,
    maximum_latitude=-10.0,
)

PROJECTIONS = (
    PROJECTION_WEB_MERCATOR,
    PROJECTION_EQUAL_EARTH,
    PROJECTION_ROBINSON,
)


def _project_ring(
    ring,
    projection,
):
    rect = _map_rect(
        PACIFIC_BOUNDS,
        QRectF(
            0.0,
            0.0,
            1200.0,
            700.0,
        ),
        projection,
    )

    points = [
        _project(
            longitude,
            latitude,
            PACIFIC_BOUNDS,
            rect,
            projection,
        )
        for longitude, latitude in ring
    ]

    return rect, points


@pytest.mark.parametrize(
    "projection",
    PROJECTIONS,
)
def test_ring_crossing_antimeridian_has_no_huge_segment(
    projection,
):
    # Synthetic island straddling ±180°.
    ring = (
        (179.0, -20.0),
        (-179.0, -20.0),
        (-179.0, -15.0),
        (179.0, -15.0),
        (179.0, -20.0),
    )

    rect, points = _project_ring(
        ring,
        projection,
    )

    horizontal_segments = [
        abs(
            current.x()
            - previous.x()
        )
        for previous, current
        in zip(points, points[1:])
    ]

    # No edge may jump across anything close to the whole map.
    assert max(horizontal_segments) < (
        rect.width() * 0.75
    )


@pytest.mark.parametrize(
    "projection",
    PROJECTIONS,
)
def test_antimeridian_edge_is_shorter_than_opposite_world_edge(
    projection,
):
    rect = _map_rect(
        PACIFIC_BOUNDS,
        QRectF(
            0.0,
            0.0,
            1200.0,
            700.0,
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

    center = _project(
        180.0,
        -17.0,
        PACIFIC_BOUNDS,
        rect,
        projection,
    )

    distance_across_dateline = abs(
        east.x() - west.x()
    )

    distance_to_center = max(
        abs(east.x() - center.x()),
        abs(west.x() - center.x()),
    )

    # 179 and -179 must behave symmetrically around 180.
    assert distance_across_dateline == pytest.approx(
        2.0 * distance_to_center,
        rel=0.05,
    )


@pytest.mark.parametrize(
    "projection",
    PROJECTIONS,
)
def test_ring_vertices_remain_inside_pacific_map(
    projection,
):
    ring = (
        (178.5, -22.0),
        (179.5, -22.0),
        (-179.5, -18.0),
        (-178.5, -18.0),
    )

    rect, points = _project_ring(
        ring,
        projection,
    )

    for point in points:
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


@pytest.mark.parametrize(
    "projection",
    PROJECTIONS,
)
def test_ordinary_european_segment_remains_ordinary(
    projection,
):
    bounds = GeographicBounds(
        minimum_longitude=-10.0,
        minimum_latitude=40.0,
        maximum_longitude=30.0,
        maximum_latitude=70.0,
    )

    rect = _map_rect(
        bounds,
        QRectF(
            0.0,
            0.0,
            1200.0,
            700.0,
        ),
        projection,
    )

    paris = _project(
        2.3522,
        48.8566,
        bounds,
        rect,
        projection,
    )

    berlin = _project(
        13.4050,
        52.5200,
        bounds,
        rect,
        projection,
    )

    assert abs(
        paris.x() - berlin.x()
    ) < rect.width() * 0.75
