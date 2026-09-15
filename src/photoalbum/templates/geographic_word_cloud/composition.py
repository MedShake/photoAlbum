from __future__ import annotations

from dataclasses import dataclass
from random import Random

from photoalbum.models import Photo


BASE_COLORS = (
    (72, 155, 207),
    (134, 96, 188),
    (76, 168, 108),
    (144, 198, 101),
    (238, 201, 88),
    (242, 162, 91),
    (228, 104, 71),
    (200, 76, 76),
    (210, 108, 162),
    (186, 94, 186),
    (90, 125, 206),
    (88, 185, 174),
)


@dataclass(frozen=True)
class GeographicWord:
    text: str
    count: int

    # Normalized page coordinates.
    x: float
    y: float
    width: float
    height: float

    font_size_pt: float

    color: tuple[int, int, int]


@dataclass(frozen=True)
class GeographicWordCloud:
    words: tuple[GeographicWord, ...]
    year: int | None
    photo_count: int
    city_count: int


@dataclass
class _CityData:
    count: int = 0
    latitude_total: float = 0.0
    longitude_total: float = 0.0

    @property
    def latitude(self) -> float:
        return (
            self.latitude_total
            / self.count
        )

    @property
    def longitude(self) -> float:
        return (
            self.longitude_total
            / self.count
        )


def _eligible_photos(
    photos: list[Photo] | tuple[Photo, ...],
    year: int | None,
) -> list[Photo]:
    result = []

    for photo in photos:
        if year is not None:
            capture = photo.capture_datetime

            if (
                capture is None
                or capture.year != year
            ):
                continue

        if (
            not photo.city
            or photo.latitude is None
            or photo.longitude is None
        ):
            continue

        result.append(photo)

    return result


def _city_data(
    photos: list[Photo],
) -> dict[str, _CityData]:
    result: dict[
        str,
        _CityData
    ] = {}

    # Same city spelling is grouped case-insensitively.
    canonical: dict[
        str,
        str
    ] = {}

    for photo in photos:
        assert photo.city is not None
        assert photo.latitude is not None
        assert photo.longitude is not None

        city = photo.city.strip()

        if not city:
            continue

        key = city.casefold()

        display = canonical.setdefault(
            key,
            city,
        )

        data = result.setdefault(
            display,
            _CityData(),
        )

        data.count += 1
        data.latitude_total += (
            photo.latitude
        )
        data.longitude_total += (
            photo.longitude
        )

    return result


def _font_size(
    count: int,
    *,
    minimum_count: int,
    maximum_count: int,
    minimum_font: float,
    maximum_font: float,
) -> float:
    if maximum_count == minimum_count:
        return (
            maximum_font
            + minimum_font
        ) / 2

    return (
        minimum_font
        + (
            count - minimum_count
        )
        * (
            maximum_font
            - minimum_font
        )
        / (
            maximum_count
            - minimum_count
        )
    )


def _word_size_mm(
    text: str,
    font_size_pt: float,
) -> tuple[float, float]:
    # The word cloud uses a controlled monospace font.
    # 0.60 em is kept as the historical width approximation
    # used by the placement algorithm.
    point_mm = 25.4 / 72.0

    height = (
        font_size_pt
        * point_mm
    )

    width = (
        len(text)
        * font_size_pt
        * 0.60
        * point_mm
    )

    return width, height


def _intersects(
    first: tuple[
        float,
        float,
        float,
        float,
    ],
    second: tuple[
        float,
        float,
        float,
        float,
    ],
) -> bool:
    x1, y1, w1, h1 = first
    x2, y2, w2, h2 = second

    return (
        x1 < x2 + w2
        and x1 + w1 > x2
        and y1 < y2 + h2
        and y1 + h1 > y2
    )


def _color_variation(
    base: tuple[int, int, int],
    random: Random,
) -> tuple[int, int, int]:
    return tuple(
        min(
            255,
            max(
                50,
                component
                + random.randint(
                    -20,
                    20,
                ),
            ),
        )
        for component in base
    )


def compose_geographic_word_cloud(
    photos: list[Photo] | tuple[Photo, ...],
    *,
    year: int | None = None,
    seed: int = 0,
    page_width_mm: float = 210.0,
    page_height_mm: float = 297.0,
    margin_mm: float = 20.0,
    minimum_font_pt: float = 10.0,
    maximum_font_pt: float = 40.0,
) -> GeographicWordCloud:
    eligible = _eligible_photos(
        photos,
        year,
    )

    cities = _city_data(
        eligible
    )

    if not cities:
        return GeographicWordCloud(
            words=(),
            year=year,
            photo_count=len(eligible),
            city_count=0,
        )

    counts = [
        value.count
        for value in cities.values()
    ]

    minimum_count = min(counts)
    maximum_count = max(counts)

    minimum_latitude = min(
        value.latitude
        for value in cities.values()
    )
    maximum_latitude = max(
        value.latitude
        for value in cities.values()
    )

    minimum_longitude = min(
        value.longitude
        for value in cities.values()
    )
    maximum_longitude = max(
        value.longitude
        for value in cities.values()
    )

    available_width = (
        page_width_mm
        - 2 * margin_mm
    )

    available_height = (
        page_height_mm
        - 2 * margin_mm
    )

    random = Random(seed)

    colors = {
        city: _color_variation(
            BASE_COLORS[
                index
                % len(BASE_COLORS)
            ],
            random,
        )
        for index, city
        in enumerate(cities)
    }

    # Largest cities first gives them priority when avoiding
    # collisions.
    ordered = sorted(
        cities.items(),
        key=lambda item: (
            -item[1].count,
            item[0].casefold(),
        ),
    )

    placed: list[
        tuple[
            float,
            float,
            float,
            float,
        ]
    ] = []

    words: list[
        GeographicWord
    ] = []

    longitude_span = (
        maximum_longitude
        - minimum_longitude
    )

    latitude_span = (
        maximum_latitude
        - minimum_latitude
    )

    directions = (
        (0, -1),
        (1, -1),
        (1, 0),
        (1, 1),
        (0, 1),
        (-1, 1),
        (-1, 0),
        (-1, -1),
    )

    for city, data in ordered:
        initial_font = _font_size(
            data.count,
            minimum_count=minimum_count,
            maximum_count=maximum_count,
            minimum_font=minimum_font_pt,
            maximum_font=maximum_font_pt,
        )

        font_size = initial_font
        placed_word = False

        while (
            font_size >= minimum_font_pt
            and not placed_word
        ):
            word_width, word_height = (
                _word_size_mm(
                    city,
                    font_size,
                )
            )

            usable_width = max(
                0.0,
                available_width
                - word_width,
            )

            usable_height = max(
                0.0,
                available_height
                - word_height,
            )

            if longitude_span == 0:
                longitude_ratio = 0.5
            else:
                longitude_ratio = (
                    data.longitude
                    - minimum_longitude
                ) / longitude_span

            if latitude_span == 0:
                latitude_ratio = 0.5
            else:
                # North at the top.
                latitude_ratio = (
                    maximum_latitude
                    - data.latitude
                ) / latitude_span

            base_x = (
                margin_mm
                + longitude_ratio
                * usable_width
            )

            base_y = (
                margin_mm
                + latitude_ratio
                * usable_height
            )

            # Original PHP behaviour: first try geographical
            # position, then eight directions with growing
            # offsets.
            offsets = range(
                0,
                52,
                2,
            )

            for offset in offsets:
                candidates = (
                    ((0, 0),)
                    if offset == 0
                    else directions
                )

                for dx, dy in candidates:
                    x = (
                        base_x
                        + dx * offset
                    )
                    y = (
                        base_y
                        + dy * offset
                    )

                    x = min(
                        max(
                            x,
                            margin_mm,
                        ),
                        page_width_mm
                        - margin_mm
                        - word_width,
                    )

                    y = min(
                        max(
                            y,
                            margin_mm,
                        ),
                        page_height_mm
                        - margin_mm
                        - word_height,
                    )

                    candidate = (
                        x,
                        y,
                        word_width,
                        word_height,
                    )

                    if any(
                        _intersects(
                            candidate,
                            existing,
                        )
                        for existing in placed
                    ):
                        continue

                    placed.append(
                        candidate
                    )

                    words.append(
                        GeographicWord(
                            text=city,
                            count=data.count,
                            x=(
                                x
                                / page_width_mm
                            ),
                            y=(
                                y
                                / page_height_mm
                            ),
                            width=(
                                word_width
                                / page_width_mm
                            ),
                            height=(
                                word_height
                                / page_height_mm
                            ),
                            font_size_pt=font_size,
                            color=colors[city],
                        )
                    )

                    placed_word = True
                    break

                if placed_word:
                    break

            if not placed_word:
                font_size -= 2.0

    return GeographicWordCloud(
        words=tuple(words),
        year=year,
        photo_count=len(eligible),
        city_count=len(cities),
    )
