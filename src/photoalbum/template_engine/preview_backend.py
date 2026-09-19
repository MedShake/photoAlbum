from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Callable,
)

from PySide6.QtGui import QPixmap

if TYPE_CHECKING:
    from photoalbum.album import PageInstance
from photoalbum.i18n import Translator


@dataclass(frozen=True)
class PreviewJob:
    worker: object

    # Called in GUI thread once worker returned its bytes.
    finalize: Callable[
        [bytes],
        QPixmap,
    ]


class TemplatePreviewBackend(ABC):
    """
    Optional backend for expensive page-template previews.

    PreviewRenderService knows this interface only. It does
    not know concrete template IDs.
    """

    template_id: str

    def effective_photos(
        self,
        instance: PageInstance,
        photos,
    ) -> tuple:
        unique = {}

        for photo in photos:
            unique.setdefault(
                str(photo.path),
                photo,
            )

        return tuple(
            sorted(
                unique.values(),
                key=lambda photo: str(
                    photo.path
                ),
            )
        )

    def render_settings_signature(
        self,
        instance: PageInstance,
    ) -> object:
        """
        Return the settings state that affects the expensive
        raster produced by this backend.

        The default keeps the historical behaviour: every setting
        participates in the preview cache key. Backends may return
        a smaller immutable value when some settings are rendered
        later as lightweight overlays.
        """
        return instance.settings

    @abstractmethod
    def create_job(
        self,
        *,
        request_id: str,
        instance: PageInstance,
        photos,
        width: int,
        height: int,
        page_width_mm: float,
        page_height_mm: float,
        translator: Translator,
    ) -> PreviewJob:
        raise NotImplementedError
