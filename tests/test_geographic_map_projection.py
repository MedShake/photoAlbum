from __future__ import annotations

from PySide6.QtCore import QRectF

from photoalbum.templates.msb.geographic_map.geography import (
    GeographicBounds,
)
from photoalbum.templates.msb.geographic_map.painter import (
    _map_rect,
    _project,
    _projected_bounds,
    _web_mercator,
)


def test_web_mercator_equator_origin():
    x, y = _web_mercator(0.0, 0.0)

    assert abs(x) < 1e-12
    assert abs(y) < 1e-12


def test_web_mercator_northing_increases_with_latitude():
    _x1, y1 = _web_mercator(0.0, 40.7128)
    _x2, y2 = _web_mercator(0.0, 48.8566)
    _x3, y3 = _web_mercator(0.0, 66.5039)

    assert y1 < y2 < y3


def test_map_rect_preserves_projected_aspect_ratio():
    # New York + France + Rovaniemi-style stress extent.
    bounds = GeographicBounds(
        minimum_longitude=-74.0060,
        minimum_latitude=40.0,
        maximum_longitude=25.7294,
        maximum_latitude=67.0,
    )

    target = QRectF(
        0.0,
        0.0,
        1200.0,
        700.0,
    )

    rect = _map_rect(bounds, target)

    min_x, min_y, max_x, max_y = _projected_bounds(
        bounds
    )

    projected_ratio = (
        (max_x - min_x)
        / (max_y - min_y)
    )

    rendered_ratio = (
        rect.width()
        / rect.height()
    )

    assert abs(
        rendered_ratio - projected_ratio
    ) < 1e-10


def test_project_uses_same_geometry_as_map_rect():
    bounds = GeographicBounds(
        minimum_longitude=-74.0060,
        minimum_latitude=40.0,
        maximum_longitude=25.7294,
        maximum_latitude=67.0,
    )

    rect = _map_rect(
        bounds,
        QRectF(
            0.0,
            0.0,
            1200.0,
            700.0,
        ),
    )

    southwest = _project(
        bounds.minimum_longitude,
        bounds.minimum_latitude,
        bounds,
        rect,
    )

    northeast = _project(
        bounds.maximum_longitude,
        bounds.maximum_latitude,
        bounds,
        rect,
    )

    assert abs(
        southwest.x() - rect.left()
    ) < 1e-9

    assert abs(
        southwest.y() - rect.bottom()
    ) < 1e-9

    assert abs(
        northeast.x() - rect.right()
    ) < 1e-9

    assert abs(
        northeast.y() - rect.top()
    ) < 1e-9


def test_render_target_shape_does_not_distort_projection():
    bounds = GeographicBounds(
        minimum_longitude=-74.0060,
        minimum_latitude=40.0,
        maximum_longitude=25.7294,
        maximum_latitude=67.0,
    )

    wide = _map_rect(
        bounds,
        QRectF(0.0, 0.0, 1400.0, 600.0),
    )

    tall = _map_rect(
        bounds,
        QRectF(0.0, 0.0, 600.0, 1400.0),
    )

    assert abs(
        wide.width() / wide.height()
        - tall.width() / tall.height()
    ) < 1e-10
