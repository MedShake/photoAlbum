from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float

    place_name: str | None = None
    city: str | None = None
    address: str | None = None

