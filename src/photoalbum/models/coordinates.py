from math import isfinite


def usable_coordinates(latitude: object, longitude: object) -> bool:
    """Accept only finite numeric GPS pairs in geographic bounds."""
    return all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and -limit <= value <= limit
        and isfinite(value)
        for value, limit in ((latitude, 90), (longitude, 180))
    )
