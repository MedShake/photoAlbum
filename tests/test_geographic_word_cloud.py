from datetime import datetime
from pathlib import Path

from photoalbum.templates.msb.geographic_word_cloud.composition import (
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


def test_word_cloud_reserves_font_line_height():
    """Word boxes leave room for font ascenders and descenders."""
    from PySide6.QtGui import (
        QGuiApplication,
    )

    from photoalbum.templates.msb.geographic_word_cloud.composition import (
        _word_size_mm,
    )
    from photoalbum.templates.msb.geographic_word_cloud.text_metrics import (
        physical_line_height_mm,
    )

    app = (
        QGuiApplication.instance()
        or QGuiApplication([])
    )

    font_size_pt = 72.0

    _, height = _word_size_mm(
        "Sydney",
        font_size_pt,
    )

    one_em_mm = (
        font_size_pt
        * 25.4
        / 72.0
    )

    assert height > one_em_mm
    assert height == physical_line_height_mm(
        font_size_pt
    )


def test_word_cloud_uses_rendered_text_width():
    """Word boxes use the rendered font advance width."""
    from PySide6.QtGui import QGuiApplication

    from photoalbum.templates.msb.geographic_word_cloud.composition import (
        _word_size_mm,
    )
    from photoalbum.templates.msb.geographic_word_cloud.text_metrics import (
        physical_text_width_mm,
    )

    app = (
        QGuiApplication.instance()
        or QGuiApplication([])
    )

    text = "Saint-Sébastien-sur-Loire"
    font_size_pt = 72.0

    width, _ = _word_size_mm(
        text,
        font_size_pt,
    )

    assert width == physical_text_width_mm(
        text,
        font_size_pt,
    )
