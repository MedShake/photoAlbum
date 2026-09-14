from datetime import datetime
from pathlib import Path

from photoalbum.album import PageInstance
from photoalbum.gui.preview_render_service import (
    PreviewRenderService,
)
from photoalbum.models import Photo


def photo(
    name: str,
    *,
    dated: bool,
) -> Photo:
    return Photo(
        path=Path(name),
        filename=name,
        capture_datetime=(
            datetime(2025, 1, 1)
            if dated
            else None
        ),
    )


def test_scatter_effective_photos_ignore_undated():
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

    first = (
        PreviewRenderService
        ._effective_photos(
            instance,
            dated,
        )
    )

    second = (
        PreviewRenderService
        ._effective_photos(
            instance,
            with_anomalies,
        )
    )

    assert first == second

    assert (
        PreviewRenderService
        ._photos_signature(first)
        ==
        PreviewRenderService
        ._photos_signature(second)
    )
