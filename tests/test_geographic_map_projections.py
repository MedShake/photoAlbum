from __future__ import annotations

from math import isfinite

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
    _project_raw,
    _projected_bounds,
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
def test_projection_origin(projection):
    x, y = _project_raw(
        0.0,
        0.0,
        projection,
    )

    assert x == pytest.approx(
        0.0,
        abs=1e-12,
    )

    assert y == pytest.approx(
        0.0,
        abs=1e-12,
    )


@pytest.mark.parametrize(
    "projection",
    PROJECTIONS,
)
def test_projection_stress_points_are_finite(
    projection,
):
    # New York, Nantes, Rovaniemi.
    for longitude, latitude in (
        (-74.0060, 40.7128),
        (-1.5536, 47.2184),
        (25.7294, 66.5039),
    ):
        x, y = _project_raw(
            longitude,
            latitude,
            projection,
        )

        assert isfinite(x)
        assert isfinite(y)


@pytest.mark.parametrize(
    "projection",
    PROJECTIONS,
)
def test_fit_keeps_projected_ratio(
    projection,
):
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
        projection,
    )

    (
        minimum_x,
        minimum_y,
        maximum_x,
        maximum_y,
    ) = _projected_bounds(
        bounds,
        projection,
    )

    expected = (
        (maximum_x - minimum_x)
        / (maximum_y - minimum_y)
    )

    actual = (
        rect.width()
        / rect.height()
    )

    assert actual == pytest.approx(
        expected,
        rel=1e-10,
    )


def test_unknown_projection_uses_mercator():
    expected = _project_raw(
        2.0,
        48.0,
        PROJECTION_WEB_MERCATOR,
    )

    actual = _project_raw(
        2.0,
        48.0,
        "unknown",
    )

    assert actual == pytest.approx(
        expected
    )
