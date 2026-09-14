from datetime import datetime
from pathlib import Path

from photoalbum.album.geographic_word_cloud import (
    compose_geographic_word_cloud,
)
from photoalbum.models import Photo


def photo(
    filename: str,
    *,
    city: str,
    year: int,
    latitude: float,
    longitude: float,
) -> Photo:
    return Photo(
        path=Path(filename),
        filename=filename,
        capture_datetime=datetime(
            year,
            6,
            1,
        ),
        city=city,
        latitude=latitude,
        longitude=longitude,
    )


def test_cloud_uses_all_years_by_default():
    photos = [
        photo(
            "paris.jpg",
            city="Paris",
            year=2024,
            latitude=48.8566,
            longitude=2.3522,
        ),
        photo(
            "lyon.jpg",
            city="Lyon",
            year=2025,
            latitude=45.7640,
            longitude=4.8357,
        ),
    ]

    cloud = compose_geographic_word_cloud(
        photos
    )

    assert {
        word.text
        for word in cloud.words
    } == {
        "Paris",
        "Lyon",
    }


def test_cloud_can_filter_one_year():
    photos = [
        photo(
            "paris.jpg",
            city="Paris",
            year=2024,
            latitude=48.8566,
            longitude=2.3522,
        ),
        photo(
            "lyon.jpg",
            city="Lyon",
            year=2025,
            latitude=45.7640,
            longitude=4.8357,
        ),
    ]

    cloud = compose_geographic_word_cloud(
        photos,
        year=2025,
    )

    assert [
        word.text
        for word in cloud.words
    ] == [
        "Lyon",
    ]


def test_frequency_controls_font_size():
    photos = [
        photo(
            "paris1.jpg",
            city="Paris",
            year=2025,
            latitude=48.8566,
            longitude=2.3522,
        ),
        photo(
            "paris2.jpg",
            city="Paris",
            year=2025,
            latitude=48.8566,
            longitude=2.3522,
        ),
        photo(
            "lyon.jpg",
            city="Lyon",
            year=2025,
            latitude=45.7640,
            longitude=4.8357,
        ),
    ]

    cloud = compose_geographic_word_cloud(
        photos
    )

    sizes = {
        word.text: word.font_size_pt
        for word in cloud.words
    }

    assert (
        sizes["Paris"]
        > sizes["Lyon"]
    )


def test_cloud_is_reproducible():
    photos = [
        photo(
            "paris.jpg",
            city="Paris",
            year=2025,
            latitude=48.8566,
            longitude=2.3522,
        ),
        photo(
            "lyon.jpg",
            city="Lyon",
            year=2025,
            latitude=45.7640,
            longitude=4.8357,
        ),
    ]

    first = compose_geographic_word_cloud(
        photos,
        seed=42,
    )

    second = compose_geographic_word_cloud(
        photos,
        seed=42,
    )

    assert first == second
