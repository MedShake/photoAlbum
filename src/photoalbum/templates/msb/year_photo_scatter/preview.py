from __future__ import annotations

from PySide6.QtGui import QPixmap

from photoalbum.album import PageInstance
from photoalbum.templates.msb.year_photo_scatter.render_worker import (
    CoverRenderWorker,
)
from photoalbum.i18n import Translator
from photoalbum.template_engine.preview_backend import (
    PreviewJob,
    TemplatePreviewBackend,
)

from .composition import (
    stored_cover_scatter,
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
                photo.identity,
                photo,
            )

        return tuple(
            sorted(
                unique.values(),
                key=lambda photo: photo.identity,
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
        *,
        template_pack_settings=None,
    ) -> object:
        # The expensive raster contains the photo scatter only.
        # Title font, size and color are painted later by the
        # lightweight widget renderer and must not invalidate it.
        scatter = instance.settings.get("scatter", {})
        proposals = scatter.get("proposals") if isinstance(scatter, dict) else None
        index = int(scatter.get("selected_seed_index", 0)) if isinstance(scatter, dict) else 0
        if isinstance(proposals, list) and 0 <= index < len(proposals):
            import hashlib
            import json
            data = json.dumps(proposals[index], sort_keys=True).encode("utf-8")
            return ("frozen", hashlib.sha256(data).hexdigest())
        return ("seed", self._seed(instance))

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
        template_pack_settings=None,
    ) -> PreviewJob:
        composition = stored_cover_scatter(
            instance,
            list(photos),
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
