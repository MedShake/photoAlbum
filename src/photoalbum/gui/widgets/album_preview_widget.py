from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import (
    QThreadPool,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QImageReader,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import (
    A4,
    AlbumBuildResult,
    AlbumStructureSettings,
    CoverPosition,
    PageFormat,
    PageSide,
    PlanItemKind,
    TemplateRegistry,
)
from photoalbum.album.month_divider_layout import (
    CLASSIC_MONTH_DIVIDER_LAYOUT,
)

from photoalbum.album.cover_scatter import (
    compose_cover_scatter,
    visible_cover_scatter_items,
)

from photoalbum.album.composition import (
    HorizontalAlignment,
    PageComposer,
    PageComposition,
    PhotoSlotComposition,
)
from photoalbum.album.geographic_word_cloud import (
    compose_geographic_word_cloud,
)
from photoalbum.gui.geographic_word_cloud_painter import (
    paint_geographic_word_cloud,
)
from photoalbum.album.calendar_index import (
    calendar_month_page_numbers,
    compose_calendar_index,
)
from photoalbum.gui.calendar_index_painter import (
    paint_calendar_index,
)
from photoalbum.gui.preview_render_service import (
    PreviewRenderService,
)
from photoalbum.templates import (
    template_extension_registry,
)
from photoalbum.i18n import Translator

from photoalbum.gui.cover_render_worker import CoverRenderWorker


PREVIEW_PAGE_WIDTH = 300


class PreviewThumbnailCache:
    """
    Shared in-memory thumbnail cache.

    Images are decoded near preview resolution rather than at
    full camera resolution.

    setAutoTransform(True) applies EXIF orientation before the
    image reaches the preview.
    """

    def __init__(self) -> None:
        self._cache: dict[
            tuple[str, int, int],
            QPixmap,
        ] = {}

    def clear(self) -> None:
        self._cache.clear()

    def load(
        self,
        path: str | Path,
        target_size: QSize,
    ) -> QPixmap:
        path = str(path)

        key = (
            path,
            target_size.width(),
            target_size.height(),
        )

        cached = self._cache.get(key)

        if cached is not None:
            return cached

        reader = QImageReader(path)
        reader.setAutoTransform(True)

        source_size = reader.size()

        if source_size.isValid():
            maximum = max(
                target_size.width(),
                target_size.height(),
            )

            decode_size = source_size.scaled(
                QSize(maximum, maximum),
                Qt.AspectRatioMode.KeepAspectRatio,
            )

            if decode_size.isValid():
                reader.setScaledSize(decode_size)

        image = reader.read()

        if image.isNull():
            pixmap = QPixmap()
        else:
            pixmap = QPixmap.fromImage(image)

        self._cache[key] = pixmap

        return pixmap


class _PreviewPageBase(QWidget):
    PAGE_WIDTH = PREVIEW_PAGE_WIDTH

    def __init__(
        self,
        *,
        page_format: PageFormat,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._page_format = page_format

        ratio = (
            page_format.height_mm
            / page_format.width_mm
        )

        self.setFixedSize(
            self.PAGE_WIDTH,
            round(self.PAGE_WIDTH * ratio),
        )

    def _pixel_rect(
        self,
        rect,
    ) -> QRect:
        return QRect(
            round(rect.x * self.width()),
            round(rect.y * self.height()),
            round(rect.width * self.width()),
            round(rect.height * self.height()),
        )

    def _print_font_pixel_size(
        self,
        points: float,
    ) -> int:
        """
        Scale a physical print font to the reduced preview.

        8 pt = about 2.82 mm on paper.
        """

        millimeters = (
            points * 25.4 / 72.0
        )

        pixels = (
            millimeters
            * self.width()
            / self._page_format.width_mm
        )

        # Keep tiny previews readable while remaining visually
        # close to the printed result.
        return max(
            5,
            round(pixels),
        )

    def _paint_paper(
        self,
        painter: QPainter,
    ) -> None:
        painter.fillRect(
            self.rect(),
            Qt.GlobalColor.white,
        )

        painter.setPen(
            QPen(Qt.GlobalColor.gray, 1)
        )

        painter.drawRect(
            self.rect().adjusted(
                0,
                0,
                -1,
                -1,
            )
        )


class AlbumCoverPreview(_PreviewPageBase):
    def __init__(
        self,
        *,
        position: CoverPosition,
        template_id: str,
        registry: TemplateRegistry,
        result: AlbumBuildResult,
        cover_settings,
        thumbnail_cache: PreviewThumbnailCache,
        page_format: PageFormat,
        translator: Translator,
        render_service: PreviewRenderService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            page_format=page_format,
            parent=parent,
        )

        self._position = position
        self._template_id = template_id
        self._registry = registry
        self._result = result
        self._cover_settings = cover_settings
        self._thumbnail_cache = thumbnail_cache
        self._translator = translator
        self._render_service = render_service

        self._shared_preview_key = None

        self._render_service.preview_ready.connect(
            self._shared_preview_ready
        )

        self._render_service.preview_failed.connect(
            self._shared_preview_failed
        )

        self._scatter_cache_key = None
        self._scatter_cache_pixmap = QPixmap()

        self._scatter_request_id = None
        self._scatter_loading = False
        self._scatter_title = ""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        self._paint_paper(painter)

        extension = (
            template_extension_registry.get(
                self._template_id
            )
        )

        template_renderer = (
            extension.widget_renderer
            if extension is not None
            else None
        )

        if template_renderer is not None:
            template_renderer.paint(
                painter=painter,
                instance=self._cover_settings.page,
                photos=self._project_photos(),
                target_rect=self.rect(),
                width=self.width(),
                height=self.height(),
                translator=self._translator,
                render_service=self._render_service,
                set_waiting_key=self._set_template_preview_key,
                font_pixel_size=self._print_font_pixel_size,
                page_width_mm=self._page_format.width_mm,
                page_height_mm=self._page_format.height_mm,
                album_pages=self._result.pagination.pages,
            )
            return


        labels = {
            CoverPosition.FRONT: (
                "preview.cover.front"
            ),
            CoverPosition.INSIDE_FRONT: (
                "preview.cover.inside_front"
            ),
            CoverPosition.INSIDE_BACK: (
                "preview.cover.inside_back"
            ),
            CoverPosition.BACK: (
                "preview.cover.back"
            ),
        }

        title = self._translator.tr(
            labels[self._position]
        )

        template = self._registry.get(
            self._template_id
        )

        template_key = (
            f"template.{template.template_id}"
        )

        template_name = self._translator.tr(
            template_key
        )

        if template_name == template_key:
            template_name = template.name

        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(
            self._print_font_pixel_size(16)
        )
        painter.setFont(font)

        painter.setPen(
            Qt.GlobalColor.darkGray
        )

        title_rect = self.rect().adjusted(
            20,
            40,
            -20,
            -80,
        )

        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignCenter,
            title,
        )

        font.setBold(False)
        font.setPixelSize(
            self._print_font_pixel_size(9)
        )
        painter.setFont(font)

        painter.drawText(
            self.rect().adjusted(
                20,
                self.height() - 70,
                -20,
                -20,
            ),
            (
                Qt.AlignmentFlag.AlignHCenter
                | Qt.AlignmentFlag.AlignTop
            ),
            template_name,
        )

    def _paint_geographic_word_cloud(
        self,
        painter: QPainter,
    ) -> None:
        settings = (
            self._cover_settings
            .page
            .settings
            .get(
                "geographic_word_cloud",
                {},
            )
        )

        if not isinstance(
            settings,
            dict,
        ):
            settings = {}

        year = settings.get(
            "year"
        )

        cloud = compose_geographic_word_cloud(
            self._project_photos(),
            year=year,
            page_width_mm=(
                self._page_format.width_mm
            ),
            page_height_mm=(
                self._page_format.height_mm
            ),
        )

        paint_geographic_word_cloud(
            painter,
            target_rect=self.rect(),
            cloud=cloud,
            page_width_mm=(
                self._page_format.width_mm
            ),
        )

        if not cloud.words:
            painter.setPen(
                Qt.GlobalColor.darkGray
            )

            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._translator.tr(
                    "page_settings.no_geographic_data"
                ),
            )

    def _paint_calendar_index(
        self,
        painter: QPainter,
    ) -> None:
        settings = (
            self._cover_settings
            .page
            .settings
            .get(
                "calendar_index",
                {},
            )
        )

        if not isinstance(
            settings,
            dict,
        ):
            settings = {}

        years = sorted(
            {
                photo.capture_datetime.year
                for photo in self._project_photos()
                if photo.capture_datetime
                is not None
            }
        )

        year = settings.get(
            "year"
        )

        if year not in years:
            year = (
                years[0]
                if years
                else None
            )

        if year is None:
            return

        page_numbers = (
            calendar_month_page_numbers(
                self._result.pagination.pages,
                year,
            )
        )

        composition = compose_calendar_index(
            self._project_photos(),
            year=year,
            month_page_numbers=page_numbers,
        )

        paint_calendar_index(
            painter,
            target_rect=self.rect(),
            composition=composition,
            translator=self._translator,
            page_width_mm=self._page_format.width_mm,
            page_height_mm=self._page_format.height_mm,
        )

    def _set_template_preview_key(
        self,
        key,
    ) -> None:
        self._shared_preview_key = key

    def _project_photos(
        self,
    ):
        photos = []
        seen = set()

        for item in self._result.plan.items:
            for photo in item.photos:
                key = str(
                    photo.path
                )

                if key in seen:
                    continue

                seen.add(
                    key
                )

                photos.append(
                    photo
                )

        return sorted(
            photos,
            key=lambda photo: str(
                photo.path
            ),
        )


    def _paint_year_photo_scatter(
        self,
        painter: QPainter,
    ) -> None:
        instance = (
            self._cover_settings.page
        )

        photos = tuple(
            self._project_photos()
        )

        key = self._render_service.key_for(
            instance,
            photos,
            width=self.width(),
            height=self.height(),
        )

        pixmap = self._render_service.cached(
            key
        )

        self._shared_preview_key = key

        if pixmap is None:
            self._render_service.request(
                instance,
                photos,
                width=self.width(),
                height=self.height(),
            )

            painter.setPen(
                Qt.GlobalColor.darkGray
            )

            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._translator.tr(
                    "page_settings.calculating"
                ),
            )

            # Remember which asynchronous result concerns
            # this widget. The connection itself is permanent.
            self._shared_preview_key = key

            return

        painter.drawPixmap(
            self.rect(),
            pixmap,
            pixmap.rect(),
        )

        scatter = instance.settings.get(
            "scatter",
            {},
        )

        seeds = (
            scatter.get(
                "seeds",
                [0],
            )
            if isinstance(
                scatter,
                dict,
            )
            else [0]
        )

        index = (
            int(
                scatter.get(
                    "selected_seed_index",
                    0,
                )
            )
            if isinstance(
                scatter,
                dict,
            )
            else 0
        )

        seeds = list(
            seeds
        ) or [0]

        index = min(
            max(
                index,
                0,
            ),
            len(seeds) - 1,
        )

        composition = compose_cover_scatter(
            photos,
            seed=int(
                seeds[index]
            ),
            month_name=(
                self._translator.month_name
            ),
        )

        self._scatter_title = (
            composition.title
        )

        self._paint_scatter_title(
            painter
        )

    def _shared_preview_ready(
        self,
        key,
    ) -> None:
        if (
            key
            != self._shared_preview_key
        ):
            return

        self.update()

    def _shared_preview_failed(
        self,
        key,
        message: str,
    ) -> None:
        if (
            key
            != self._shared_preview_key
        ):
            return

        self.update()

    def _start_scatter_render(
        self,
        cache_key,
        composition,
    ) -> None:
        request_id = uuid4().hex

        self._scatter_request_id = request_id
        self._scatter_loading = True
        self._scatter_cache_key = cache_key
        self._scatter_title = composition.title

        worker = CoverRenderWorker(
            request_id=request_id,
            width=self.width(),
            height=self.height(),
            items=visible_cover_scatter_items(
                composition.items
            ),
        )

        worker.signals.finished.connect(
            self._scatter_render_ready
        )

        worker.signals.failed.connect(
            self._scatter_render_failed
        )

        QThreadPool.globalInstance().start(
            worker
        )

    def _scatter_render_ready(
        self,
        request_id: str,
        data: bytes,
    ) -> None:
        if (
            request_id
            != self._scatter_request_id
        ):
            return

        pixmap = QPixmap()
        pixmap.loadFromData(data)

        if pixmap.isNull():
            return

        self._scatter_cache_pixmap = pixmap
        self._scatter_loading = False

        self.update()

    def _scatter_render_failed(
        self,
        request_id: str,
        message: str,
    ) -> None:
        if (
            request_id
            != self._scatter_request_id
        ):
            return

        self._scatter_loading = False
        self.update()

    def _scatter_title_color(
        self,
    ) -> QColor:
        try:
            settings = (
                self._cover_settings.page.settings
            )

            scatter = settings.get(
                "scatter",
                {},
            )

            value = (
                scatter.get(
                    "title_color",
                    "#d0d0d0",
                )
                if isinstance(
                    scatter,
                    dict,
                )
                else "#d0d0d0"
            )
        except Exception:
            value = "#d0d0d0"

        color = QColor(
            str(value)
        )

        if not color.isValid():
            color = QColor(
                "#d0d0d0"
            )

        return color

    def _paint_scatter_title(
        self,
        painter: QPainter,
    ) -> None:
        font = QFont(
            painter.font()
        )

        font.setBold(True)
        font.setPixelSize(
            self._print_font_pixel_size(
                72
            )
        )

        painter.setFont(font)
        painter.setPen(
            self._scatter_title_color()
        )

        painter.drawText(
            self.rect().adjusted(
                15,
                15,
                -15,
                -15,
            ),
            Qt.AlignmentFlag.AlignCenter,
            self._scatter_title,
        )


class AlbumPagePreview(_PreviewPageBase):
    def __init__(
        self,
        composition: PageComposition,
        *,
        thumbnail_cache: PreviewThumbnailCache,
        page_format: PageFormat = A4,
        translator: Translator | None = None,
        project_photos=None,
        album_pages=None,
        render_service=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            page_format=page_format,
            parent=parent,
        )

        self._composition = composition
        self._thumbnail_cache = thumbnail_cache
        self._translator = (
            translator
            or Translator("en")
        )

        self._project_photos = tuple(
            project_photos or ()
        )

        self._album_pages = tuple(
            album_pages or ()
        )

        # Async state for instantiated special-page scatter.
        self._special_scatter_request_id = None
        self._special_scatter_cache_key = None
        self._special_scatter_pixmap = QPixmap()
        self._special_scatter_loading = False
        self._special_scatter_title = ""
        self._render_service = render_service
        self._shared_preview_key = None

        if self._render_service is not None:
            self._render_service.preview_ready.connect(
                self._shared_template_preview_ready
            )
            self._render_service.preview_failed.connect(
                self._shared_template_preview_failed
            )


    def paintEvent(
        self,
        event,
    ) -> None:
        painter = QPainter(self)

        self._paint_paper(painter)

        page = self._composition.page

        if (
            page.kind == PlanItemKind.SPECIAL_PAGE
            and page.page_instance is not None
            and self._render_template_special_page(
                painter
            )
        ):
            pass

        elif (
            page.kind == PlanItemKind.PHOTO_GROUP
            and self._render_template_page(
                painter
            )
        ):
            pass

        elif (
            page.kind
            == PlanItemKind.MONTH_DIVIDER
            and self._render_template_page(
                painter
            )
        ):
            pass

        elif (
            page.kind == PlanItemKind.YEAR_DIVIDER
            and self._render_template_page(
                painter
            )
        ):
            pass

        else:
            self._paint_non_photo_page(
                painter
            )

        self._paint_page_number(
            painter
        )

    def _special_scatter_seed(
        self,
    ) -> int:
        page = self._composition.page

        instance = page.page_instance

        if instance is None:
            return 0

        scatter = instance.settings.get(
            "scatter",
            {},
        )

        if not isinstance(
            scatter,
            dict,
        ):
            return 0

        seeds = scatter.get(
            "seeds",
            [0],
        )

        if not isinstance(
            seeds,
            (list, tuple),
        ):
            seeds = [0]

        seeds = [
            int(value)
            for value in seeds
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

    def _paint_special_scatter(
        self,
        painter: QPainter,
    ) -> None:
        page = self._composition.page

        instance = page.page_instance

        if instance is None:
            return

        seed = self._special_scatter_seed()

        composition = compose_cover_scatter(
            list(self._project_photos),
            seed=seed,
            month_name=self._translator.month_name,
        )

        cache_key = (
            instance.instance_id,
            seed,
            composition.title,
            len(composition.items),
            self.width(),
            self.height(),
        )

        if (
            self._special_scatter_cache_key
            != cache_key
            and not self._special_scatter_loading
        ):
            self._start_special_scatter_render(
                cache_key,
                composition,
            )

        if (
            self._special_scatter_pixmap.isNull()
        ):
            painter.setPen(
                Qt.GlobalColor.darkGray
            )

            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._translator.tr(
                    "page_settings.calculating"
                ),
            )

            return

        painter.drawPixmap(
            0,
            0,
            self._special_scatter_pixmap,
        )

        self._paint_special_scatter_title(
            painter
        )

        if self._special_scatter_loading:
            painter.fillRect(
                self.rect(),
                QColor(
                    255,
                    255,
                    255,
                    150,
                ),
            )

            painter.setPen(
                Qt.GlobalColor.darkGray
            )

            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._translator.tr(
                    "page_settings.calculating"
                ),
            )

    def _start_special_scatter_render(
        self,
        cache_key,
        composition,
    ) -> None:
        request_id = uuid4().hex

        self._special_scatter_request_id = (
            request_id
        )

        self._special_scatter_cache_key = (
            cache_key
        )

        self._special_scatter_loading = True

        self._special_scatter_title = (
            composition.title
        )

        worker = CoverRenderWorker(
            request_id=request_id,
            width=self.width(),
            height=self.height(),
            items=visible_cover_scatter_items(
                composition.items
            ),
        )

        worker.signals.finished.connect(
            self._special_scatter_ready
        )

        worker.signals.failed.connect(
            self._special_scatter_failed
        )

        QThreadPool.globalInstance().start(
            worker
        )

    def _special_scatter_ready(
        self,
        request_id: str,
        data: bytes,
    ) -> None:
        if (
            request_id
            != self._special_scatter_request_id
        ):
            return

        pixmap = QPixmap()
        pixmap.loadFromData(
            data
        )

        if pixmap.isNull():
            self._special_scatter_loading = False
            self.update()
            return

        self._special_scatter_pixmap = pixmap
        self._special_scatter_loading = False

        self.update()

    def _special_scatter_failed(
        self,
        request_id: str,
        message: str,
    ) -> None:
        if (
            request_id
            != self._special_scatter_request_id
        ):
            return

        self._special_scatter_loading = False

        self.update()

    def _special_scatter_title_color(
        self,
    ) -> QColor:
        page = self._composition.page

        instance = page.page_instance

        value = "#d0d0d0"

        if instance is not None:
            scatter = instance.settings.get(
                "scatter",
                {},
            )

            if isinstance(
                scatter,
                dict,
            ):
                value = str(
                    scatter.get(
                        "title_color",
                        "#d0d0d0",
                    )
                )

        color = QColor(
            value
        )

        if not color.isValid():
            color = QColor(
                "#d0d0d0"
            )

        return color

    def _paint_special_scatter_title(
        self,
        painter: QPainter,
    ) -> None:
        font = QFont(
            painter.font()
        )

        font.setBold(True)

        font.setPixelSize(
            self._print_font_pixel_size(
                72
            )
        )

        painter.setFont(
            font
        )

        painter.setPen(
            self._special_scatter_title_color()
        )

        painter.drawText(
            self.rect().adjusted(
                15,
                15,
                -15,
                -15,
            ),
            Qt.AlignmentFlag.AlignCenter,
            self._special_scatter_title,
        )

    def _paint_special_geographic_word_cloud(
        self,
        painter: QPainter,
    ) -> None:
        page = self._composition.page

        instance = page.page_instance

        if instance is None:
            return

        settings = instance.settings.get(
            "geographic_word_cloud",
            {},
        )

        if not isinstance(
            settings,
            dict,
        ):
            settings = {}

        year = settings.get(
            "year"
        )

        cloud = compose_geographic_word_cloud(
            list(
                self._project_photos
            ),
            year=year,
            page_width_mm=(
                self._page_format.width_mm
            ),
            page_height_mm=(
                self._page_format.height_mm
            ),
        )

        paint_geographic_word_cloud(
            painter,
            target_rect=self.rect(),
            cloud=cloud,
            page_width_mm=(
                self._page_format.width_mm
            ),
        )

        if not cloud.words:
            painter.setPen(
                Qt.GlobalColor.darkGray
            )

            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._translator.tr(
                    "page_settings.no_geographic_data"
                ),
            )

    def _paint_special_calendar_index(
        self,
        painter: QPainter,
    ) -> None:
        page = self._composition.page

        instance = page.page_instance

        if instance is None:
            return

        settings = instance.settings.get(
            "calendar_index",
            {},
        )

        if not isinstance(
            settings,
            dict,
        ):
            settings = {}

        years = sorted(
            {
                photo.capture_datetime.year
                for photo in self._project_photos
                if photo.capture_datetime
                is not None
            }
        )

        year = settings.get(
            "year"
        )

        if year not in years:
            year = (
                years[0]
                if years
                else None
            )

        if year is None:
            return

        page_numbers = (
            calendar_month_page_numbers(
                self._album_pages,
                year,
            )
        )

        composition = compose_calendar_index(
            self._project_photos,
            year=year,
            month_page_numbers=page_numbers,
        )

        paint_calendar_index(
            painter,
            target_rect=self.rect(),
            composition=composition,
            translator=self._translator,
            page_width_mm=self._page_format.width_mm,
            page_height_mm=self._page_format.height_mm,
        )

    def _set_template_preview_key(
        self,
        key,
    ) -> None:
        self._shared_preview_key = key

    def _shared_template_preview_ready(
        self,
        key,
    ) -> None:
        if key != self._shared_preview_key:
            return

        self.update()

    def _shared_template_preview_failed(
        self,
        key,
        message: str,
    ) -> None:
        if key != self._shared_preview_key:
            return

        self.update()

    def _render_template_special_page(
        self,
        painter: QPainter,
    ) -> bool:
        page = self._composition.page

        instance = page.page_instance

        if (
            instance is None
            or self._render_service is None
        ):
            return False

        extension = (
            template_extension_registry.get(
                instance.template_id
            )
        )

        renderer = (
            extension.widget_renderer
            if extension is not None
            else None
        )

        if renderer is None:
            return False

        renderer.paint(
            painter=painter,
            instance=instance,
            photos=self._project_photos,
            target_rect=self.rect(),
            width=self.width(),
            height=self.height(),
            translator=self._translator,
            render_service=self._render_service,
            set_waiting_key=self._set_template_preview_key,
            font_pixel_size=self._print_font_pixel_size,
            page_width_mm=self._page_format.width_mm,
            page_height_mm=self._page_format.height_mm,
            album_pages=self._album_pages,
        )

        return True

    def _render_template_page(
        self,
        painter: QPainter,
    ) -> bool:
        """
        Generic rendering of a normal album page through its
        registered template extension.

        The core knows the page kind, never the concrete
        template implementation.
        """

        page = self._composition.page

        extension = (
            template_extension_registry.get(
                page.template_id
            )
        )

        renderer = (
            extension.widget_renderer
            if extension is not None
            else None
        )

        if renderer is None:
            return False

        renderer.paint(
            painter=painter,
            instance=page.page_instance,
            photos=page.photos,
            target_rect=self.rect(),
            width=self.width(),
            height=self.height(),
            translator=self._translator,
            render_service=self._render_service,
            set_waiting_key=self._set_template_preview_key,
            font_pixel_size=self._print_font_pixel_size,
            page_width_mm=self._page_format.width_mm,
            page_height_mm=self._page_format.height_mm,
            album_pages=self._album_pages,
            composition=self._composition,
            thumbnail_cache=self._thumbnail_cache,
            pixel_rect=self._pixel_rect,
        )

        return True

    def _paint_photo_page(
        self,
        painter: QPainter,
    ) -> None:
        page = self._composition.page

        for index, slot in enumerate(
            self._composition.photo_slots
        ):
            if index >= len(page.photos):
                self._paint_empty_slot(
                    painter,
                    slot,
                )
                continue

            photo = page.photos[index]

            self._paint_photo(
                painter,
                slot,
                photo.path,
            )

            self._paint_caption(
                painter,
                slot,
            )

    def _paint_photo(
        self,
        painter: QPainter,
        slot: PhotoSlotComposition,
        path: Path,
    ) -> None:
        rect = self._pixel_rect(
            slot.image_rect
        )

        pixmap = self._thumbnail_cache.load(
            path,
            rect.size(),
        )

        if pixmap.isNull():
            painter.setPen(
                QPen(Qt.GlobalColor.gray, 1)
            )

            painter.drawRect(rect)

            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                self._translator.tr(
                    "preview.image_unavailable"
                ),
            )
            return

        scaled = pixmap.scaled(
            rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = (
            rect.x()
            + (rect.width() - scaled.width()) // 2
        )
        y = (
            rect.y()
            + (rect.height() - scaled.height()) // 2
        )

        painter.drawPixmap(
            x,
            y,
            scaled,
        )

    def _paint_empty_slot(
        self,
        painter: QPainter,
        slot: PhotoSlotComposition,
    ) -> None:
        rect = self._pixel_rect(
            slot.image_rect
        )

        painter.setPen(
            QPen(
                Qt.GlobalColor.lightGray,
                1,
                Qt.PenStyle.DashLine,
            )
        )

        painter.drawRect(rect)

    def _paint_caption(
        self,
        painter: QPainter,
        slot: PhotoSlotComposition,
    ) -> None:
        if (
            slot.caption_rect is None
            or slot.caption.is_empty
        ):
            return

        rect = self._pixel_rect(
            slot.caption_rect
        )

        lines: list[str] = []

        if slot.caption.capture_datetime is not None:
            lines.append(
                slot.caption.capture_datetime.strftime(
                    "%d/%m/%Y %H:%M"
                )
            )

        if slot.caption.location_text:
            lines.append(
                slot.caption.location_text
            )

        font = QFont(painter.font())

        # Historical template: 8 pt on the printed page.
        # The font is scaled to the miniature size here.
        font.setPixelSize(
            self._print_font_pixel_size(8)
        )

        painter.setFont(font)
        painter.setPen(
            Qt.GlobalColor.black
        )

        painter.drawText(
            rect,
            (
                Qt.AlignmentFlag.AlignHCenter
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap
            ),
            "\n".join(lines),
        )

    def _paint_page_number(
        self,
        painter: QPainter,
    ) -> None:
        page_number = (
            self._composition.page_number
        )

        if page_number is None:
            return

        rect = self._pixel_rect(
            page_number.rect
        )

        if (
            page_number.alignment
            == HorizontalAlignment.LEFT
        ):
            alignment = Qt.AlignmentFlag.AlignLeft
        else:
            alignment = Qt.AlignmentFlag.AlignRight

        font = QFont(painter.font())
        font.setPixelSize(
            self._print_font_pixel_size(8)
        )
        painter.setFont(font)

        painter.setPen(
            Qt.GlobalColor.black
        )

        painter.drawText(
            rect,
            (
                alignment
                | Qt.AlignmentFlag.AlignVCenter
            ),
            str(page_number.number),
        )

    def _paint_month_divider(
        self,
        painter: QPainter,
    ) -> None:
        page = self._composition.page

        if (
            page.year is None
            or page.month is None
        ):
            return

        layout = CLASSIC_MONTH_DIVIDER_LAYOUT

        month_name = (
            self._translator.month_name(
                page.month
            )
        )

        if month_name:
            month_name = (
                month_name[:1].upper()
                + month_name[1:]
            )

        title = (
            f"{month_name} {page.year}"
        )

        red, green, blue = (
            layout.color_for_month(
                page.month
            )
        )

        painter.setPen(
            QColor(
                red,
                green,
                blue,
            )
        )

        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(
            self._print_font_pixel_size(
                layout.title_font_pt
            )
        )
        painter.setFont(font)

        painter.drawText(
            self._pixel_rect(
                layout.title_rect
            ),
            (
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
            title,
        )

        if not page.cities:
            return

        painter.setPen(
            Qt.GlobalColor.black
        )

        font = QFont(painter.font())
        font.setBold(False)
        font.setPixelSize(
            self._print_font_pixel_size(
                layout.cities_font_pt
            )
        )
        painter.setFont(font)

        painter.drawText(
            self._pixel_rect(
                layout.cities_rect
            ),
            (
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignTop
                | Qt.TextFlag.TextWordWrap
            ),
            "\n".join(page.cities),
        )

    def _paint_non_photo_page(
        self,
        painter: QPainter,
    ) -> None:
        page = self._composition.page

        if page.blank_reason is not None:
            text = self._translator.tr(
                "preview.blank_page"
            )

        elif page.kind == PlanItemKind.MONTH_DIVIDER:
            text = self._translator.tr(
                "preview.month_divider"
            )

        elif page.kind == PlanItemKind.YEAR_DIVIDER:
            text = self._translator.tr(
                "preview.year_divider"
            )

        elif page.kind == PlanItemKind.SPECIAL_PAGE:
            text = self._translator.tr(
                "preview.special_page"
            )

        else:
            text = ""

        painter.setPen(
            Qt.GlobalColor.darkGray
        )

        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(
            self._print_font_pixel_size(14)
        )
        painter.setFont(font)

        painter.drawText(
            self.rect().adjusted(
                20,
                20,
                -20,
                -20,
            ),
            Qt.AlignmentFlag.AlignCenter,
            text,
        )


class AlbumPreviewWidget(QWidget):
    """
    Physical book preview.

    Front cover:
        [ empty ][ front ]

    Opening spread:
        [ inside front ][ page 1 ]

    Interior:
        [ page 2 ][ page 3 ]
        ...

    Closing:
        [ last left ][ inside back ]
        or, when the interior ends on a right page:
        [ empty ][ inside back ]

    Back cover:
        [ back ][ empty ]
    """

    SPREAD_HORIZONTAL_GAP = 18
    SPREAD_VERTICAL_GAP = 28

    def __init__(
        self,
        registry: TemplateRegistry,
        translator: Translator | None = None,
        render_service: PreviewRenderService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._registry = registry
        self._translator = translator or Translator("en")
        self._render_service = (
            render_service
            or PreviewRenderService(
                self._translator,
                self,
            )
        )

        self._composer = PageComposer()
        self._thumbnail_cache = PreviewThumbnailCache()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)

        self._content = QWidget()

        self._pages_grid = QGridLayout(
            self._content
        )

        self._pages_grid.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignTop
        )

        self._pages_grid.setHorizontalSpacing(
            self.SPREAD_HORIZONTAL_GAP
        )

        self._pages_grid.setVerticalSpacing(
            self.SPREAD_VERTICAL_GAP
        )

        self._scroll.setWidget(
            self._content
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self._scroll)

    def clear(self) -> None:
        while self._pages_grid.count():
            item = self._pages_grid.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self._thumbnail_cache.clear()

    def _cover_widget(
        self,
        settings: AlbumStructureSettings,
        position: CoverPosition,
        page_format: PageFormat,
    ) -> AlbumCoverPreview:
        cover = settings.covers[position]

        return AlbumCoverPreview(
            position=position,
            template_id=cover.template_id,
            registry=self._registry,
            result=self._current_result,
            cover_settings=cover,
            thumbnail_cache=self._thumbnail_cache,
            page_format=page_format,
            translator=self._translator,
            render_service=self._render_service,
        )

    def set_result(
        self,
        result: AlbumBuildResult,
        settings: AlbumStructureSettings,
        *,
        page_format: PageFormat = A4,
    ) -> None:
        self.clear()
        self._current_result = result

        # Row 0: outer front cover, right side.
        self._pages_grid.addWidget(
            self._cover_widget(
                settings,
                CoverPosition.FRONT,
                page_format,
            ),
            0,
            1,
            Qt.AlignmentFlag.AlignTop,
        )

        # Row 1: inside front cover on the left.
        self._pages_grid.addWidget(
            self._cover_widget(
                settings,
                CoverPosition.INSIDE_FRONT,
                page_format,
            ),
            1,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        pages = result.pagination.pages

        # One canonical list of project photos for templates
        # that operate on the whole album, such as scatter.
        project_photos = []
        seen_photo_paths = set()

        for plan_item in result.plan.items:
            for photo in plan_item.photos:
                key = str(
                    photo.path
                )

                if key in seen_photo_paths:
                    continue

                seen_photo_paths.add(
                    key
                )

                project_photos.append(
                    photo
                )

        # Interior starts on the right opposite the inside
        # front cover.
        for page in pages:
            composition = self._composer.compose(
                page,
                settings.photo_pages,
                settings.page_numbers,
            )

            preview = AlbumPagePreview(
                composition,
                thumbnail_cache=self._thumbnail_cache,
                page_format=page_format,
                translator=self._translator,
                render_service=self._render_service,
                project_photos=project_photos,
                album_pages=result.pagination.pages,
            )

            # Interior spread row:
            # p1 -> row 1 right
            # p2/p3 -> row 2
            # p4/p5 -> row 3
            row = 1 + (page.number // 2)

            column = (
                0
                if page.side == PageSide.LEFT
                else 1
            )

            self._pages_grid.addWidget(
                preview,
                row,
                column,
                Qt.AlignmentFlag.AlignTop,
            )

        if pages:
            last_page = pages[-1]

            if last_page.side == PageSide.LEFT:
                inside_back_row = (
                    1 + (last_page.number // 2)
                )
            else:
                inside_back_row = (
                    2 + (last_page.number // 2)
                )
        else:
            inside_back_row = 1

        # Inside back cover is a right-facing page.
        self._pages_grid.addWidget(
            self._cover_widget(
                settings,
                CoverPosition.INSIDE_BACK,
                page_format,
            ),
            inside_back_row,
            1,
            Qt.AlignmentFlag.AlignTop,
        )

        # Outside back cover is displayed alone on the left.
        self._pages_grid.addWidget(
            self._cover_widget(
                settings,
                CoverPosition.BACK,
                page_format,
            ),
            inside_back_row + 1,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
