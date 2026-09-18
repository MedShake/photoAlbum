from datetime import datetime
from pathlib import Path

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
    ) == service.key_for(
        second,
        photos,
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
    ) != service.key_for(
        second,
        photos,
    )
