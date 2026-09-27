from __future__ import annotations

from functools import lru_cache

from math import asin, cos, log, pi, radians, sin, sqrt, tan

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
)

from photoalbum.rendering.fonts import resolve_font_family

from .composition import GeographicMap
from .geography import (
    GeographicBounds,
    country_components,
    world_offsets,
    longitude_near_reference,
)


DEFAULT_LAND_COLOR = QColor("#ffffff")
DEFAULT_WATER_COLOR = QColor("#eaf2f4")
DEFAULT_BORDER_COLOR = QColor("#b8aa98")
DEFAULT_MARKER_COLOR = QColor("#695237")


# Web Mercator becomes singular at the geographic poles.
_WEB_MERCATOR_MAX_LATITUDE = 85.0511287798066

PROJECTION_WEB_MERCATOR = "web_mercator"
PROJECTION_EQUAL_EARTH = "equal_earth"
PROJECTION_ROBINSON = "robinson"

SUPPORTED_PROJECTIONS = (
    PROJECTION_WEB_MERCATOR,
    PROJECTION_EQUAL_EARTH,
    PROJECTION_ROBINSON,
)


def _normalize_projection(
    projection: str,
) -> str:
    if projection in SUPPORTED_PROJECTIONS:
        return projection

    return PROJECTION_WEB_MERCATOR


def _web_mercator(
    longitude: float,
    latitude: float,
) -> tuple[float, float]:
    latitude = max(
        -_WEB_MERCATOR_MAX_LATITUDE,
        min(
            _WEB_MERCATOR_MAX_LATITUDE,
            float(latitude),
        ),
    )

    longitude_radians = radians(
        float(longitude)
    )
    latitude_radians = radians(
        latitude
    )

    return (
        longitude_radians,
        log(
            tan(
                pi / 4.0
                + latitude_radians / 2.0
            )
        ),
    )


def _equal_earth(
    longitude: float,
    latitude: float,
) -> tuple[float, float]:
    a1 = 1.340264
    a2 = -0.081106
    a3 = 0.000893
    a4 = 0.003796

    longitude_radians = radians(
        float(longitude)
    )

    latitude_radians = radians(
        max(
            -90.0,
            min(
                90.0,
                float(latitude),
            ),
        )
    )

    theta = asin(
        sqrt(3.0)
        / 2.0
        * sin(latitude_radians)
    )

    theta2 = theta * theta
    theta4 = theta2 * theta2
    theta6 = theta4 * theta2

    denominator = (
        3.0
        * (
            9.0 * a4 * theta6
            + 7.0 * a3 * theta4
            + 3.0 * a2 * theta2
            + a1
        )
    )

    x = (
        2.0
        * sqrt(3.0)
        * longitude_radians
        * cos(theta)
        / denominator
    )

    y = theta * (
        a1
        + a2 * theta2
        + a3 * theta4
        + a4 * theta6
    )

    return x, y


_ROBINSON_X = (
    1.0000,
    0.9986,
    0.9954,
    0.9900,
    0.9822,
    0.9730,
    0.9600,
    0.9427,
    0.9216,
    0.8962,
    0.8679,
    0.8350,
    0.7986,
    0.7597,
    0.7186,
    0.6732,
    0.6213,
    0.5722,
    0.5322,
)

_ROBINSON_Y = (
    0.0000,
    0.0620,
    0.1240,
    0.1860,
    0.2480,
    0.3100,
    0.3720,
    0.4340,
    0.4958,
    0.5571,
    0.6176,
    0.6769,
    0.7346,
    0.7903,
    0.8435,
    0.8936,
    0.9394,
    0.9761,
    1.0000,
)


def _robinson_interpolate(
    values: tuple[float, ...],
    latitude: float,
) -> float:
    latitude = max(
        0.0,
        min(
            90.0,
            latitude,
        ),
    )

    if latitude >= 90.0:
        return values[-1]

    index = int(
        latitude // 5.0
    )

    fraction = (
        latitude
        - index * 5.0
    ) / 5.0

    return (
        values[index]
        + (
            values[index + 1]
            - values[index]
        )
        * fraction
    )


def _robinson(
    longitude: float,
    latitude: float,
) -> tuple[float, float]:
    latitude = max(
        -90.0,
        min(
            90.0,
            float(latitude),
        ),
    )

    absolute_latitude = abs(
        latitude
    )

    x_scale = _robinson_interpolate(
        _ROBINSON_X,
        absolute_latitude,
    )

    y_scale = _robinson_interpolate(
        _ROBINSON_Y,
        absolute_latitude,
    )

    x = (
        0.8487
        * radians(
            float(longitude)
        )
        * x_scale
    )

    y = (
        1.3523
        * y_scale
    )

    if latitude < 0.0:
        y = -y

    return x, y


def _project_raw(
    longitude: float,
    latitude: float,
    projection: str,
) -> tuple[float, float]:
    projection = _normalize_projection(
        projection
    )

    if (
        projection
        == PROJECTION_EQUAL_EARTH
    ):
        return _equal_earth(
            longitude,
            latitude,
        )

    if (
        projection
        == PROJECTION_ROBINSON
    ):
        return _robinson(
            longitude,
            latitude,
        )

    return _web_mercator(
        longitude,
        latitude,
    )


@lru_cache(maxsize=128)
def _projected_bounds(
    bounds: GeographicBounds,
    projection: str = PROJECTION_WEB_MERCATOR,
) -> tuple[float, float, float, float]:
    # All three projections have monotone northing and an easting of
    # longitude * f(abs(latitude)), with f decreasing toward the poles.
    # Their exact rectangle extrema lie at the edges or the equator.
    center = (bounds.minimum_longitude + bounds.maximum_longitude) / 2
    latitudes = [bounds.minimum_latitude, bounds.maximum_latitude]
    if bounds.minimum_latitude < 0 < bounds.maximum_latitude:
        latitudes.append(0.0)
    points = [
        _project_raw(longitude - center, latitude, projection)
        for longitude in (bounds.minimum_longitude, bounds.maximum_longitude)
        for latitude in latitudes
    ]
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _map_rect(
    bounds: GeographicBounds,
    target_rect: QRectF,
    projection: str = PROJECTION_WEB_MERCATOR,
) -> QRectF:
    (
        minimum_x,
        minimum_y,
        maximum_x,
        maximum_y,
    ) = _projected_bounds(
        bounds,
        projection,
    )

    projected_width = (
        maximum_x
        - minimum_x
    )

    projected_height = (
        maximum_y
        - minimum_y
    )

    if (
        projected_width <= 0.0
        or projected_height <= 0.0
    ):
        return QRectF(
            target_rect
        )

    margin = min(
        target_rect.width(),
        target_rect.height(),
    ) * 0.04

    available = (
        target_rect.adjusted(
            margin,
            margin,
            -margin,
            -margin,
        )
    )

    # Same scale for X and Y:
    # exactly the same principle as fitting
    # a photograph without changing its ratio.
    scale = min(
        available.width()
        / projected_width,
        available.height()
        / projected_height,
    )

    width = (
        projected_width
        * scale
    )

    height = (
        projected_height
        * scale
    )

    return QRectF(
        available.center().x()
        - width / 2.0,
        available.center().y()
        - height / 2.0,
        width,
        height,
    )


def _project_continuous(
    longitude: float,
    latitude: float,
    bounds: GeographicBounds,
    rect: QRectF,
    projection: str = PROJECTION_WEB_MERCATOR,
    projected_bounds: tuple[
        float,
        float,
        float,
        float,
    ] | None = None,
) -> QPointF:
    if projected_bounds is None:
        projected_bounds = _projected_bounds(
            bounds,
            projection,
        )

    (
        minimum_x,
        minimum_y,
        maximum_x,
        maximum_y,
    ) = projected_bounds

    # Geometry is already placed. Never choose a world copy per vertex.
    longitude -= (bounds.minimum_longitude + bounds.maximum_longitude) / 2

    (
        projected_x,
        projected_y,
    ) = _project_raw(
        longitude,
        latitude,
        projection,
    )

    width = (
        maximum_x
        - minimum_x
    )

    height = (
        maximum_y
        - minimum_y
    )

    x = (
        0.5
        if width == 0.0
        else (
            projected_x
            - minimum_x
        ) / width
    )

    y = (
        0.5
        if height == 0.0
        else (
            maximum_y
            - projected_y
        ) / height
    )

    return QPointF(
        rect.left()
        + x * rect.width(),
        rect.top()
        + y * rect.height(),
    )


def _project(longitude, latitude, bounds, rect,
             projection=PROJECTION_WEB_MERCATOR, projected_bounds=None):
    """Project an independent marker into the viewport's nearest world copy."""
    center = (bounds.minimum_longitude + bounds.maximum_longitude) / 2
    return _project_continuous(
        longitude_near_reference(longitude, center), latitude,
        bounds, rect, projection, projected_bounds,
    )


def _clip_world(ring, minimum, maximum):
    """Clip a closed polygon at the selected world's seam before projection.

    Intersections close along the seam; no artificial edge crosses the map.
    Pixel clipping remains QPainter's responsibility.
    """
    for boundary, sign in ((minimum, 1), (maximum, -1)):
        output = []
        if not ring:
            break
        previous = ring[-1]
        previous_inside = sign * (previous[0] - boundary) >= 0
        for current in ring:
            inside = sign * (current[0] - boundary) >= 0
            if inside != previous_inside:
                fraction = (boundary - previous[0]) / (current[0] - previous[0])
                output.append((boundary, previous[1] + fraction * (current[1] - previous[1])))
            if inside:
                output.append(current)
            previous, previous_inside = current, inside
        ring = output
    return tuple(ring)


def _visible_rings(bounds):
    center = (bounds.minimum_longitude + bounds.maximum_longitude) / 2
    for _country, ring, extent in country_components():
        for offset in world_offsets(extent, bounds):
            placed = tuple((longitude + offset, latitude) for longitude, latitude in ring)
            clipped = _clip_world(placed, center - 180, center + 180)
            if len(clipped) >= 3:
                yield clipped


def _paint_month_legend(
    painter: QPainter,
    rect: QRectF,
    *,
    month_colors: dict[int, QColor],
    month_labels: dict[int, str],
    months: tuple[int, ...],
    font_family: str | None = None,
) -> None:
    """One proportional layout in logical pixels, independent of device DPI."""
    if rect.width() <= 0 or rect.height() <= 0:
        return

    if not months:
        return

    # The physical width of one month cell is fixed by
    # _month_legend_rect().  Derive the painter scale from that cell,
    # rather than from the complete legend width: removing months must
    # remove cells, not shrink the remaining dots and labels.
    logical_cell_width = 1000.0 / 12.0
    cell_width = rect.width() / len(months)
    scale = cell_width / logical_cell_width

    painter.save()
    painter.translate(rect.topLeft())
    painter.scale(scale, scale)

    logical_width = logical_cell_width * len(months)
    height = rect.height() / scale

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 230))
    painter.drawRoundedRect(
        QRectF(0, 0, logical_width, height),
        10,
        10,
    )

    # Explicit theme font: do not inherit bold or point sizing from a page
    # title. Text, dots and spacing share the same scaling in preview/PDF.
    font = QFont(resolve_font_family(font_family))
    font.setPixelSize(14)
    painter.setFont(font)
    metrics = QFontMetricsF(font)

    radius = 5.0
    gap = 7.0
    labels = [
        (month, month_labels.get(month, str(month)))
        for month in months
    ]
    longest = max(
        metrics.horizontalAdvance(label)
        for _month, label in labels
    )
    text_scale = min(
        1.0,
        (logical_cell_width - 28.0)
        / max(longest, 1.0),
    )

    for index, (month, label) in enumerate(labels):
        label_width = metrics.horizontalAdvance(label) * text_scale
        group_width = 2 * radius + gap + label_width
        left = (
            index * logical_cell_width
            + (logical_cell_width - group_width) / 2
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(month_colors[month])
        painter.drawEllipse(QPointF(left + radius, height / 2), radius, radius)

        painter.save()
        painter.translate(left + 2 * radius + gap, height / 2)
        painter.scale(text_scale, text_scale)
        painter.setPen(QColor("#222222"))
        painter.drawText(
            QPointF(0, (metrics.ascent() - metrics.descent()) / 2), label,
        )
        painter.restore()

    painter.restore()



def _month_legend_rect(
    rect: QRectF,
    month_count: int,
) -> QRectF:
    """Return a centred legend with one fixed-width cell per month."""
    month_count = max(
        0,
        min(12, int(month_count)),
    )

    maximum_width = rect.width() * 0.86
    cell_width = maximum_width / 12.0
    legend_width = cell_width * month_count
    legend_height = maximum_width * 0.044

    return QRectF(
        rect.center().x() - legend_width / 2.0,
        rect.bottom()
        - legend_height
        - rect.height() * 0.025,
        legend_width,
        legend_height,
    )


def paint_geographic_map(
    painter: QPainter,
    rect: QRectF,
    composition: GeographicMap,
    *,
    land_color: QColor | None = None,
    water_color: QColor | None = None,
    border_color: QColor | None = None,
    marker_color: QColor | None = None,
    month_colors: dict[int, QColor] | None = None,
    point_color_mode: str = "single",
    point_size: float = 0.0035,
    point_opacity: float = 0.72,
    show_month_legend: bool = False,
    month_labels: dict[int, str] | None = None,
    projection: str = PROJECTION_WEB_MERCATOR,
    legend_font_family: str | None = None,
) -> None:
    land = land_color or DEFAULT_LAND_COLOR
    water = water_color or DEFAULT_WATER_COLOR
    border = border_color or DEFAULT_BORDER_COLOR
    marker = marker_color or DEFAULT_MARKER_COLOR

    painter.save()

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(rect, water)

    painter.setClipRect(rect, Qt.ClipOperation.IntersectClip)

    show_legend = (
        show_month_legend
        and point_color_mode == "month"
        and month_colors is not None
        and month_labels is not None
    )

    # The legend is an overlay. It must never change
    # the geographic framing of the map.
    projection = _normalize_projection(
        projection
    )

    map_rect = _map_rect(
        composition.bounds,
        rect,
        projection,
    )

    projected_bounds = _projected_bounds(
        composition.bounds,
        projection,
    )

    legend_rect = QRectF()

    border_pen = QPen(border)
    border_pen.setWidthF(max(0.6, min(rect.width(), rect.height()) * 0.0015))
    border_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    painter.setPen(border_pen)
    painter.setBrush(land)

    for ring in _visible_rings(composition.bounds):
        path = QPainterPath()
        for index, (longitude, latitude) in enumerate(ring):
            point = _project_continuous(
                longitude, latitude, composition.bounds, map_rect,
                projection, projected_bounds,
            )
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        path.closeSubpath()
        painter.drawPath(path)

    radius = max(
        1.0,
        min(rect.width(), rect.height())
        * max(0.001, float(point_size)),
    )

    opacity = max(
        0.0,
        min(1.0, float(point_opacity)),
    )

    painter.setPen(Qt.PenStyle.NoPen)

    for item in composition.markers:
        color = QColor(marker)

        if (
            point_color_mode == "month"
            and month_colors is not None
            and item.month in month_colors
        ):
            color = QColor(
                month_colors[item.month]
            )

        color.setAlphaF(opacity)
        painter.setBrush(color)

        point = _project(
            item.longitude,
            item.latitude,
            composition.bounds,
            map_rect,
            projection,
            projected_bounds,
        )

        painter.drawEllipse(
            point,
            radius,
            radius,
        )

    if show_legend:
        legend_months = tuple(
            sorted(
                {
                    item.month
                    for item in composition.markers
                    if item.month in month_colors
                }
            )
        )

        if legend_months:
            legend_rect = _month_legend_rect(
                rect,
                len(legend_months),
            )

            _paint_month_legend(
                painter,
                legend_rect,
                month_colors=month_colors,
                month_labels=month_labels,
                months=legend_months,
                font_family=legend_font_family,
            )

    painter.restore()
