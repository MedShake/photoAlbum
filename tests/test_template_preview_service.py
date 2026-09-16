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


def test_service_detects_expensive_scatter_backend():
    ensure_app()
    register_discovered_template_extensions()

    service = PreviewRenderService(
        Translator("fr")
    )

    assert service.supports(
        "year-photo-scatter"
    )


def test_service_does_not_require_backend_for_light_template():
    ensure_app()
    register_discovered_template_extensions()

    service = PreviewRenderService(
        Translator("fr")
    )

    assert not service.supports(
        "calendar-index"
    )


def test_effective_scatter_photos_are_owned_by_backend():
    ensure_app()
    register_discovered_template_extensions()

    service = PreviewRenderService(
        Translator("fr")
    )

    instance = PageInstance(
        template_id="year-photo-scatter"
    )

    dated = Photo(
        path=Path("dated.jpg"),
        filename="dated.jpg",
        capture_datetime=datetime(
            2025,
            1,
            1,
        ),
    )

    undated = Photo(
        path=Path("undated.jpg"),
        filename="undated.jpg",
    )

    photos = service.effective_photos(
        instance,
        [
            dated,
            undated,
        ],
    )

    assert photos == (
        dated,
    )
