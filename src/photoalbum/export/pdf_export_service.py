from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    QMarginsF,
    QRect,
    QSizeF,
)
from PySide6.QtGui import (
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
)

from photoalbum.album.builder import AlbumBuildResult
from photoalbum.album.composition import PageComposer
from photoalbum.album.models import CoverPosition
from photoalbum.album.settings import AlbumStructureSettings
from photoalbum.templates import template_extension_registry
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.rendering import (
    PageRenderGeometry,
    PageRenderer,
    RenderImageCache,
)


@dataclass(frozen=True)
class PdfMetadata:
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""


class PdfExportService:
    """
    Render an AlbumBuildResult to a final PDF document.

    Album pagination and template composition are not rebuilt
    here. The exporter consumes the exact same compositions as
    the GUI preview.
    """

    def __init__(
        self,
        translator: Translator,
    ) -> None:
        self._translator = translator
        self._page_renderer = PageRenderer(
            translator=translator,
        )
        self._page_composer = PageComposer()

    def export(
        self,
        *,
        output_path: Path,
        result: AlbumBuildResult,
        settings: AlbumStructureSettings,
        photos: list[Photo],
        page_width_mm: float,
        page_height_mm: float,
        dpi: int,
        metadata: PdfMetadata | None = None,
        progress_callback: (
            Callable[[int, int, str], None]
            | None
        ) = None,
    ) -> None:
        if dpi <= 0:
            raise ValueError(
                "PDF DPI must be greater than zero."
            )

        if page_width_mm <= 0 or page_height_mm <= 0:
            raise ValueError(
                "PDF page dimensions must be greater than zero."
            )

        pages = tuple(
            result.pagination.pages
        )

        if not pages:
            raise ValueError(
                "The album contains no page to export."
            )

        total_output_pages = (
            len(pages) + 4
        )
        completed_output_pages = 0

        def report_progress(
            message: str,
        ) -> None:
            nonlocal completed_output_pages

            completed_output_pages += 1

            if progress_callback is not None:
                progress_callback(
                    completed_output_pages,
                    total_output_pages,
                    message,
                )

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        writer = QPdfWriter(
            str(output_path)
        )

        writer.setResolution(
            dpi
        )

        page_size = QPageSize(
            QSizeF(
                page_width_mm,
                page_height_mm,
            ),
            QPageSize.Unit.Millimeter,
            "Photo Album",
            QPageSize.SizeMatchPolicy.ExactMatch,
        )

        page_layout = QPageLayout(
            page_size,
            QPageLayout.Orientation.Portrait,
            QMarginsF(
                0.0,
                0.0,
                0.0,
                0.0,
            ),
            QPageLayout.Unit.Millimeter,
        )

        writer.setPageLayout(
            page_layout
        )

        metadata = metadata or PdfMetadata()

        if metadata.title:
            writer.setTitle(
                metadata.title
            )

        if metadata.author:
            writer.setCreator(
                metadata.author
            )

        # QPdfWriter does not expose the complete PDF metadata
        # dictionary uniformly across supported Qt versions.
        #
        # Subject and keywords remain part of our public export
        # model so they can be written when the backend supports
        # them without changing the GUI contract.

        image_cache = RenderImageCache()

        # Use the exact same canonical project-photo list as
        # AlbumPreviewWidget. Some templates, notably covers,
        # operate on the whole album rather than on one page.
        project_photos = []
        seen_photo_paths = set()

        for plan_item in result.plan.items:
            for photo in plan_item.photos:
                key = str(photo.path)

                if key in seen_photo_paths:
                    continue

                seen_photo_paths.add(key)
                project_photos.append(photo)

        project_photos.sort(
            key=lambda photo: str(photo.path)
        )

        painter = QPainter()

        if not painter.begin(writer):
            raise RuntimeError(
                f"Could not create PDF: {output_path}"
            )

        # Use the actual paint device dimensions reported by
        # QPdfWriter. This keeps normalized geometry, fonts and
        # images in the exact same coordinate system.
        width = writer.width()
        height = writer.height()

        if width <= 0 or height <= 0:
            painter.end()
            raise RuntimeError(
                "PDF writer reported an invalid page size: "
                f"{width}x{height}"
            )

        geometry = PageRenderGeometry(
            width=width,
            height=height,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
        )

        target_rect = QRect(
            0,
            0,
            width,
            height,
        )

        try:
            first_output_page = True

            def begin_output_page() -> None:
                nonlocal first_output_page

                if first_output_page:
                    first_output_page = False
                else:
                    if not writer.newPage():
                        raise RuntimeError(
                            "Could not create the next PDF page."
                        )

                painter.fillRect(
                    target_rect,
                    0xFFFFFFFF,
                )

            def paint_cover(
                position: CoverPosition,
            ) -> None:
                cover = settings.covers[position]

                extension = (
                    template_extension_registry.get(
                        cover.template_id
                    )
                )

                renderer = (
                    extension.widget_renderer
                    if extension is not None
                    else None
                )

                if renderer is None:
                    raise RuntimeError(
                        "No renderer registered for cover "
                        f"template: {cover.template_id}"
                    )

                begin_output_page()

                renderer.paint(
                    painter=painter,
                    instance=cover.page,
                    photos=project_photos,
                    target_rect=target_rect,
                    width=width,
                    height=height,
                    translator=self._translator,
                    render_service=None,
                    set_waiting_key=None,
                    font_pixel_size=(
                        geometry.font_pixel_size
                    ),
                    page_width_mm=page_width_mm,
                    page_height_mm=page_height_mm,
                    album_pages=pages,
                    thumbnail_cache=image_cache,
                )

                cover_labels = {
                    CoverPosition.FRONT:
                        "Première de couverture",
                    CoverPosition.INSIDE_FRONT:
                        "Intérieur de couverture avant",
                    CoverPosition.INSIDE_BACK:
                        "Intérieur de couverture arrière",
                    CoverPosition.BACK:
                        "Quatrième de couverture",
                }

                report_progress(
                    cover_labels.get(
                        position,
                        "Couverture",
                    )
                )

            # Physical document order, identical to Preview.
            paint_cover(
                CoverPosition.FRONT
            )

            paint_cover(
                CoverPosition.INSIDE_FRONT
            )

            for page_number, page in enumerate(
                pages,
                start=1,
            ):
                composition = self._page_composer.compose(
                    page,
                    settings.photo_pages,
                    settings.page_numbers,
                    page_width_mm=page_width_mm,
                    page_height_mm=page_height_mm,
                )

                begin_output_page()

                self._page_renderer.paint(
                    painter=painter,
                    composition=composition,
                    target_rect=target_rect,
                    width=width,
                    height=height,
                    page_width_mm=page_width_mm,
                    page_height_mm=page_height_mm,
                    font_pixel_size=(
                        geometry.font_pixel_size
                    ),
                    pixel_rect=(
                        geometry.pixel_rect
                    ),
                    thumbnail_cache=image_cache,
                    project_photos=project_photos,
                    album_pages=pages,
                    render_service=None,
                    set_waiting_key=None,
                    paint_fallback=None,
                    show_empty_slots=False,
                )

                report_progress(
                    f"Page {page_number}"
                )

            paint_cover(
                CoverPosition.INSIDE_BACK
            )

            paint_cover(
                CoverPosition.BACK
            )

        finally:
            painter.end()

        if (
            not output_path.exists()
            or output_path.stat().st_size == 0
        ):
            raise RuntimeError(
                f"PDF was not created: {output_path}"
            )
