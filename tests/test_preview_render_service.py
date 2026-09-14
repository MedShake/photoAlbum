from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication

from photoalbum.album import PageInstance
from photoalbum.gui.preview_render_service import (
    PreviewRenderService,
)
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.templates import (
    register_builtin_template_extensions,
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

    register_builtin_template_extensions()

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
