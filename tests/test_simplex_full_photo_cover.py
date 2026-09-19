from pathlib import Path
from types import SimpleNamespace

import pytest

from photoalbum.album import PageInstance
from photoalbum.templates.simplex.full_photo_cover.geometry import (
    centered_cover_crop,
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
