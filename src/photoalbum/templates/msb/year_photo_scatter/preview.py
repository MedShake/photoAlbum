from __future__ import annotations

from PySide6.QtGui import QPixmap

from photoalbum.album import PageInstance
from photoalbum.rendering.cover_render_worker import (
    CoverRenderWorker,
)
from photoalbum.i18n import Translator
from photoalbum.template_engine.preview_backend import (
    PreviewJob,
    TemplatePreviewBackend,
)

from .composition import (
    compose_cover_scatter,
    visible_cover_scatter_items,
)


class YearPhotoScatterPreviewBackend(
    TemplatePreviewBackend
):
    template_id = "year-photo-scatter"

    def effective_photos(
        self,
        instance: PageInstance,
        photos,
    ) -> tuple:
        unique = {}

        for photo in photos:
            # Business rule of THIS template.
            if photo.capture_datetime is None:
                continue

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

    @staticmethod
    def _seed(
        instance: PageInstance,
    ) -> int:
        scatter = instance.settings.get(
            "scatter",
            {},
        )

        if not isinstance(
            scatter,
            dict,
        ):
            scatter = {}

        seeds = [
            int(value)
            for value in scatter.get(
                "seeds",
                [0],
            )
        ] or [0]

        index = int(
            scatter.get(
                "selected_seed_index",
                0,
            )
        )

        index = min(
            max(index, 0),
            len(seeds) - 1,
        )

        return seeds[index]

    def render_settings_signature(
        self,
        instance: PageInstance,
    ) -> object:
        # The expensive raster contains the photo scatter only.
        # Title font, size and color are painted later by the
        # lightweight widget renderer and must not invalidate it.
        return (
            "seed",
            self._seed(instance),
        )

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
        composition = compose_cover_scatter(
            list(photos),
            seed=self._seed(
                instance
            ),
            month_name=(
                translator.month_name
            ),
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
        )

        worker = CoverRenderWorker(
            request_id=request_id,
            width=width,
            height=height,
            items=visible_cover_scatter_items(
                composition.items
            ),
        )

        # For now the shared worker output stays identical to
        # the current cache behaviour. Text overlays continue
        # to be handled by the existing widget/settings editor.
        def finalize(
            data: bytes,
        ) -> QPixmap:
            pixmap = QPixmap()

            pixmap.loadFromData(
                data
            )

            return pixmap

        return PreviewJob(
            worker=worker,
            finalize=finalize,
        )
