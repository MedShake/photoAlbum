from datetime import datetime
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    ("page_width_mm", "page_height_mm"),
    [
        (210.0, 297.0),
        (215.9, 279.4),
        (297.0, 210.0),
        (250.0, 250.0),
    ],
)
def test_cloud_stays_inside_arbitrary_page_geometry(
    page_width_mm,
    page_height_mm,
):
    """Cloud composition stays inside any physical page geometry."""
    photos = [
        photo(
            "saint-sebastien.jpg",
            city="Saint-Sébastien-sur-Loire",
            year=2025,
            latitude=47.2077,
            longitude=-1.5033,
        ),
        photo(
            "paris.jpg",
            city="Paris",
            year=2025,
            latitude=48.8566,
            longitude=2.3522,
        ),
        photo(
            "toulouse.jpg",
            city="Toulouse",
            year=2025,
            latitude=43.6047,
            longitude=1.4442,
        ),
        photo(
            "brest.jpg",
            city="Brest",
            year=2025,
            latitude=48.3904,
            longitude=-4.4861,
        ),
    ]

    cloud = compose_geographic_word_cloud(
        photos,
        page_width_mm=page_width_mm,
        page_height_mm=page_height_mm,
        seed=42,
    )

    assert cloud.words

    for word in cloud.words:
        assert 0.0 <= word.x <= 1.0
        assert 0.0 <= word.y <= 1.0
        assert 0.0 < word.width <= 1.0
        assert 0.0 < word.height <= 1.0

        assert word.x + word.width <= 1.0 + 1e-9
        assert word.y + word.height <= 1.0 + 1e-9


def test_widget_renderer_forwards_physical_page_geometry(
    monkeypatch,
):
    """Renderer forwards the actual physical page geometry."""
    import photoalbum.templates.msb.geographic_word_cloud.widget_renderer as module

    captured = {}

    class DummyCloud:
        # Non vide pour éviter la branche d'affichage
        # "aucun mot" du renderer.
        words = [object()]

    def capture_compose(
        photos,
        *,
        year=None,
        page_width_mm=210.0,
        page_height_mm=297.0,
        palette=None,
        **kwargs,
    ):
        captured["page_width_mm"] = page_width_mm
        captured["page_height_mm"] = page_height_mm
        return DummyCloud()

    monkeypatch.setattr(
        module,
        "compose_geographic_word_cloud",
        capture_compose,
    )

    monkeypatch.setattr(
        module,
        "paint_geographic_word_cloud",
        lambda *args, **kwargs: None,
    )

    class DummyInstance:
        settings = {}

    renderer = module.GeographicWordCloudWidgetRenderer()

    renderer.paint(
        painter=object(),
        instance=DummyInstance(),
        photos=[],
        target_rect=None,
        width=1000,
        height=700,
        translator=None,
        render_service=None,
        set_waiting_key=lambda value: None,
        font_pixel_size=lambda value: int(value),
        page_width_mm=297.0,
        page_height_mm=210.0,
    )

    assert captured == {
        "page_width_mm": 297.0,
        "page_height_mm": 210.0,
    }
