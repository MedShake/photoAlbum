from datetime import datetime
from pathlib import Path

import pytest

from PySide6.QtWidgets import QApplication

from photoalbum.album import PageInstance
from photoalbum.gui.preview_render_service import (
    PreviewRenderService,
)
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.template_engine import (
    register_discovered_template_extensions,
)


def ensure_app():
    if QApplication.instance() is None:
        QApplication([])


def photo(
    name: str,
    *,
    dated: bool,
) -> Photo:
    return Photo(
        path=Path(name),
        filename=name,
        capture_datetime=(
            datetime(
                2025,
                1,
                1,
            )
            if dated
            else None
        ),
    )


def test_scatter_effective_photos_ignore_undated():
    ensure_app()

    register_discovered_template_extensions()

    service = PreviewRenderService(
        Translator("fr")
    )

    instance = PageInstance(
        template_id="year-photo-scatter"
    )

    dated = [
        photo(
            f"{index}.jpg",
            dated=True,
        )
        for index in range(3)
    ]

    with_anomalies = dated + [
        photo(
            "undated-1.jpg",
            dated=False,
        ),
        photo(
            "undated-2.jpg",
            dated=False,
        ),
    ]

    first = service.effective_photos(
        instance,
        dated,
    )

    second = service.effective_photos(
        instance,
        with_anomalies,
    )

    assert first == second

    assert (
        service._photos_signature(
            first
        )
        ==
        service._photos_signature(
            second
        )
    )

def test_scatter_title_style_does_not_invalidate_raster_cache_key():
    ensure_app()
    register_discovered_template_extensions()

    service = PreviewRenderService(
        Translator("fr")
    )

    photos = [
        photo(
            "1.jpg",
            dated=True,
        )
    ]

    first = PageInstance(
        template_id="year-photo-scatter",
        instance_id="same-instance",
        settings={
            "scatter": {
                "seeds": [123],
                "selected_seed_index": 0,
                "title_font_size": 72,
                "title_font_family": "Sans Serif",
                "title_color": "#ffffff",
            }
        },
    )

    second = PageInstance(
        template_id="year-photo-scatter",
        instance_id="same-instance",
        settings={
            "scatter": {
                "seeds": [123],
                "selected_seed_index": 0,
                "title_font_size": 38.5,
                "title_font_family": "Serif",
                "title_color": "#000000",
            }
        },
    )

    assert service.key_for(
        first,
        photos,
        page_width_mm=210.0,
        page_height_mm=297.0,
    ) == service.key_for(
        second,
        photos,
        page_width_mm=210.0,
        page_height_mm=297.0,
    )


def test_scatter_seed_change_invalidates_raster_cache_key():
    ensure_app()
    register_discovered_template_extensions()

    service = PreviewRenderService(
        Translator("fr")
    )

    photos = [
        photo(
            "1.jpg",
            dated=True,
        )
    ]

    first = PageInstance(
        template_id="year-photo-scatter",
        instance_id="same-instance",
        settings={
            "scatter": {
                "seeds": [123, 456],
                "selected_seed_index": 0,
            }
        },
    )

    second = PageInstance(
        template_id="year-photo-scatter",
        instance_id="same-instance",
        settings={
            "scatter": {
                "seeds": [123, 456],
                "selected_seed_index": 1,
            }
        },
    )

    assert service.key_for(
        first,
        photos,
        page_width_mm=210.0,
        page_height_mm=297.0,
    ) != service.key_for(
        second,
        photos,
        page_width_mm=210.0,
        page_height_mm=297.0,
    )


def test_scatter_orientation_changes_key_but_display_size_does_not():
    ensure_app()
    register_discovered_template_extensions()
    service = PreviewRenderService(Translator("en"))
    instance = PageInstance(template_id="year-photo-scatter")
    photos = [photo("1.jpg", dated=True)]
    portrait = service.key_for(
        instance, photos, page_width_mm=210.0, page_height_mm=297.0,
        width=420, height=594,
    )
    assert portrait == service.key_for(
        instance, photos, page_width_mm=210.0, page_height_mm=297.0,
        width=210, height=297,
    )
    assert portrait != service.key_for(
        instance, photos, page_width_mm=297.0, page_height_mm=210.0,
    )


@pytest.mark.parametrize("changes", [
    {"capture_datetime": datetime(2026, 2, 3)}, {"width": 1200},
    {"height": 800}, {"orientation": 6}, {"modified_time_ns": 123},
    {"filename": "renamed.jpg"}, {"path": Path("other.jpg")},
])
def test_scatter_photo_composition_data_invalidates_cache(changes):
    from dataclasses import replace

    ensure_app()
    register_discovered_template_extensions()
    service = PreviewRenderService(Translator("en"))
    instance = PageInstance(template_id="year-photo-scatter")
    original = photo("1.jpg", dated=True)
    geometry = dict(page_width_mm=210.0, page_height_mm=297.0)
    assert service.key_for(instance, [original], **geometry) != service.key_for(
        instance, [replace(original, **changes)], **geometry,
    )


def test_scatter_requests_reuse_title_changes_and_propagate_oriented_geometry():
    from dataclasses import replace
    from types import SimpleNamespace
    from unittest.mock import Mock

    ensure_app()
    register_discovered_template_extensions()
    service = PreviewRenderService(Translator("en"))
    service._thread_pool = SimpleNamespace(start=Mock())
    instance = PageInstance(template_id="year-photo-scatter", settings={"scatter": {"seeds": [12]}})
    photos = [photo("1.jpg", dated=True)]
    geometry = dict(width=200, height=300, page_width_mm=210.0, page_height_mm=297.0)
    first = service.request(instance, photos, **geometry)
    changed_title = replace(instance, settings={"scatter": {
        "seeds": [12], "title_font_family": "DejaVu Serif", "title_font_size": 80,
        "title_color": "#123456",
    }})
    assert service.request(changed_title, photos, **geometry) == first
    assert service._thread_pool.start.call_count == 1
    landscape = service.request(instance, photos, **{
        **geometry, "page_width_mm": 297.0, "page_height_mm": 210.0,
    })
    assert landscape != first
    assert (first.width, first.height) == (420, 594)
    assert (landscape.width, landscape.height) == (594, 420)
    assert service._thread_pool.start.call_count == 2
    # Compare worker geometry with the synchronous compositor used by PDF.
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        compose_cover_scatter, visible_cover_scatter_items,
    )
    worker = service._thread_pool.start.call_args.args[0]
    expected = compose_cover_scatter(photos, seed=12, month_name=service._translator.month_name,
                                     page_width_mm=297.0, page_height_mm=210.0)
    assert worker.items == tuple(visible_cover_scatter_items(expected.items))
    assert (worker.width, worker.height) == (594, 420)
    changed_seed = replace(instance, settings={"scatter": {"seeds": [13]}})
    assert service.request(changed_seed, photos, **geometry) != first
    assert service._thread_pool.start.call_count == 3
