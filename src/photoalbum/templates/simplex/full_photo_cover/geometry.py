from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoverCrop:
    x: float
    y: float
    width: float
    height: float


def centered_cover_crop(
    source_width: float,
    source_height: float,
    target_width: float,
    target_height: float,
) -> CoverCrop | None:
    """
    Source rectangle for an aspect-ratio preserving full-bleed cover.

    The source is scaled until the target is completely filled.
    Overflow is cropped equally on opposite sides.
    """
    if (
        source_width <= 0
        or source_height <= 0
        or target_width <= 0
        or target_height <= 0
    ):
        return None

    source_ratio = source_width / source_height
    target_ratio = target_width / target_height

    if source_ratio > target_ratio:
        height = source_height
        width = height * target_ratio
        return CoverCrop(
            x=(source_width - width) / 2.0,
            y=0.0,
            width=width,
            height=height,
        )

    width = source_width
    height = width / target_ratio

    return CoverCrop(
        x=0.0,
        y=(source_height - height) / 2.0,
        width=width,
        height=height,
    )
