from pathlib import Path
from types import SimpleNamespace

import pytest

from photoalbum.album import PageInstance
from photoalbum.templates.simplex.full_photo_cover.geometry import (
    centered_cover_crop,
)
from photoalbum.templates.simplex.full_photo_cover.title import (
    DEFAULT_TITLE_COLOR,
    automatic_title,
    default_title_font_size,
    title_color,
    title_font_size,
    title_mode,
    title_position,
    title_visible,
)
from photoalbum.templates.simplex.full_photo_cover.widget_renderer import (
    selected_photo,
)


def test_cover_crop_landscape_source_on_portrait_page():
    crop = centered_cover_crop(
        4000,
        2000,
        210,
        297,
    )

    assert crop is not None
    assert crop.height == pytest.approx(2000)
    assert crop.width == pytest.approx(
        2000 * 210 / 297
    )
    assert crop.x > 0
    assert crop.y == pytest.approx(0)


def test_cover_crop_portrait_source_on_landscape_page():
    crop = centered_cover_crop(
        2000,
        4000,
        297,
        210,
    )

    assert crop is not None
    assert crop.width == pytest.approx(2000)
    assert crop.height == pytest.approx(
        2000 * 210 / 297
    )
    assert crop.x == pytest.approx(0)
    assert crop.y > 0


def test_cover_crop_same_ratio_uses_full_source():
    crop = centered_cover_crop(
        2000,
        1000,
        400,
        200,
    )

    assert crop is not None
    assert crop.x == pytest.approx(0)
    assert crop.y == pytest.approx(0)
    assert crop.width == pytest.approx(2000)
    assert crop.height == pytest.approx(1000)


@pytest.mark.parametrize(
    "values",
    [
        (0, 100, 100, 100),
        (100, 0, 100, 100),
        (100, 100, 0, 100),
        (100, 100, 100, 0),
    ],
)
def test_cover_crop_rejects_invalid_dimensions(values):
    assert centered_cover_crop(*values) is None


def test_selected_photo_uses_persisted_path():
    photos = (
        SimpleNamespace(path=Path("/tmp/a.jpg")),
        SimpleNamespace(path=Path("/tmp/b.jpg")),
    )

    instance = PageInstance(
        template_id="simplex-full-photo-cover",
        settings={
            "photo_path": "/tmp/b.jpg",
        },
    )

    assert selected_photo(
        instance,
        photos,
    ) is photos[1]


def test_selected_photo_defaults_to_first_photo():
    photos = (
        SimpleNamespace(path=Path("/tmp/a.jpg")),
        SimpleNamespace(path=Path("/tmp/b.jpg")),
    )

    instance = PageInstance(
        template_id="simplex-full-photo-cover",
    )

    assert selected_photo(
        instance,
        photos,
    ) is photos[0]


def test_selected_photo_does_not_replace_missing_explicit_choice():
    photos = (
        SimpleNamespace(path=Path("/tmp/a.jpg")),
    )

    instance = PageInstance(
        template_id="simplex-full-photo-cover",
        settings={
            "photo_path": "/tmp/missing.jpg",
        },
    )

    assert selected_photo(
        instance,
        photos,
    ) is None


def test_simplex_pack_is_discovered():
    from photoalbum.template_engine.discovery import (
        discover_template_packs,
    )

    packs = {
        pack.pack_id: pack
        for pack in discover_template_packs()
    }

    assert "simplex" in packs

    pack = packs["simplex"]

    assert pack.name == "Simplex"

    templates = {
        template.template_id: template
        for template in pack.templates
    }

    assert "simplex-full-photo-cover" in templates

    template = templates[
        "simplex-full-photo-cover"
    ]

    assert template.pack_id == "simplex"
    assert template.pack_name == "Simplex"


def test_simplex_extension_is_registered():
    from photoalbum.template_engine import (
        template_extension_registry,
    )
    from photoalbum.template_engine.discovery import (
        register_discovered_template_extensions,
    )

    register_discovered_template_extensions()

    extension = template_extension_registry.get(
        "simplex-full-photo-cover"
    )

    assert extension is not None
    assert extension.settings_editor_type is not None
    assert extension.widget_renderer is not None


def _dated_photo(value):
    from datetime import datetime

    return SimpleNamespace(
        capture_datetime=datetime.fromisoformat(value)
    )


def test_simplex_automatic_title_without_dated_photo_is_empty():
    photos = [
        SimpleNamespace(capture_datetime=None),
    ]

    assert automatic_title(
        photos,
        lambda month: "unused",
    ) == ""


def test_simplex_automatic_title_for_single_month():
    months = {
        5: "mai",
    }

    photos = [
        _dated_photo("2024-05-02T10:00:00"),
        _dated_photo("2024-05-29T18:00:00"),
    ]

    assert automatic_title(
        photos,
        months.get,
    ) == "Mai 2024"


def test_simplex_automatic_title_for_single_year():
    photos = [
        _dated_photo("2024-01-02T10:00:00"),
        _dated_photo("2024-11-29T18:00:00"),
    ]

    assert automatic_title(
        photos,
        lambda month: str(month),
    ) == "2024"


def test_simplex_automatic_title_for_year_range():
    photos = [
        _dated_photo("2022-12-31T10:00:00"),
        _dated_photo("2025-01-01T18:00:00"),
    ]

    assert automatic_title(
        photos,
        lambda month: str(month),
    ) == "2022–2025"


def test_simplex_title_defaults():
    settings = {}

    assert title_visible(settings) is True
    assert title_mode(settings) == "automatic"
    assert title_position(settings) == "center"
    assert title_color(settings) == DEFAULT_TITLE_COLOR


def test_simplex_invalid_title_mode_and_position_use_defaults():
    settings = {
        "title": {
            "mode": "invalid",
            "position": "invalid",
        }
    }

    assert title_mode(settings) == "automatic"
    assert title_position(settings) == "center"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("2024", 72.0),
        ("2022–2025", 52.0),
        ("2022-2025", 52.0),
        ("Mai 2024", 44.0),
    ],
)
def test_simplex_default_title_font_size(title, expected):
    assert default_title_font_size(title) == expected


def test_simplex_persisted_title_font_size_is_preserved():
    settings = {
        "title": {
            "font_size": 63.5,
        }
    }

    assert title_font_size(
        settings,
        "2024",
    ) == 63.5


@pytest.mark.parametrize(
    "value",
    [
        "invalid",
        0,
        301,
        float("inf"),
    ],
)
def test_simplex_invalid_title_font_size_uses_automatic_default(value):
    settings = {
        "title": {
            "font_size": value,
        }
    }

    assert title_font_size(
        settings,
        "2024",
    ) == 72.0
