from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar


_T = TypeVar("_T")


_COMPONENT_LEVELS = (
    frozenset(
        {
            "attraction",
            "tourism",
            "amenity",
            "historic",
            "building",
            "name",
            "landmark",
            "aerialway",
            "leisure",
            "shop",
            "office",
        }
    ),
    frozenset({"house_number"}),
    frozenset(
        {
            "road",
            "route",
            "pedestrian",
            "square",
            "residential",
            "footway",
            "path",
        }
    ),
    frozenset({"neighbourhood", "quarter"}),
    frozenset({"suburb", "borough"}),
    frozenset({"city_district", "district"}),
    frozenset(
        {
            "city",
            "town",
            "village",
            "municipality",
            "hamlet",
            "isolated_dwelling",
        }
    ),
    frozenset({"county", "state_district"}),
    frozenset({"state", "region"}),
    frozenset({"postcode"}),
    frozenset({"country"}),
)

_COMPONENT_RANK = {
    key: level
    for level, keys in enumerate(_COMPONENT_LEVELS)
    for key in keys
}


def order_location_components(values: Iterable[_T]) -> tuple[_T, ...]:
    """Order keyed location values from precise to general.

    Objects only need a string ``key`` attribute. Unknown keys are kept after
    known categories in their original, stable order.
    """
    indexed = list(enumerate(values))
    unknown_rank = len(_COMPONENT_LEVELS)
    indexed.sort(
        key=lambda item: (
            _COMPONENT_RANK.get(
                str(getattr(item[1], "key", "")).casefold(),
                unknown_rank,
            ),
            item[0],
        )
    )
    return tuple(value for _index, value in indexed)
