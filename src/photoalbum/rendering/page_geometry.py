from __future__ import annotations

from PySide6.QtCore import QRect


class PageRenderGeometry:
    """
    Conversion between normalized album coordinates,
    physical print units and renderer pixels.
    """

    def __init__(
        self,
        *,
        width: int,
        height: int,
        page_width_mm: float,
        page_height_mm: float,
    ) -> None:
        self.width = width
        self.height = height
        self.page_width_mm = page_width_mm
        self.page_height_mm = page_height_mm

    def pixel_rect(
        self,
        rect,
    ) -> QRect:
        return QRect(
            round(rect.x * self.width),
            round(rect.y * self.height),
            round(rect.width * self.width),
            round(rect.height * self.height),
        )

    def font_pixel_size(
        self,
        points: float,
    ) -> int:
        """
        Convert a physical point size to renderer pixels.

        1 point = 1/72 inch.
        """

        millimeters = (
            points * 25.4 / 72.0
        )

        pixels = (
            millimeters
            * self.width
            / self.page_width_mm
        )

        return max(
            1,
            round(pixels),
        )
