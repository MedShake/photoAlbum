from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    QRect,
    QSize,
    QTimer,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
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


from photoalbum.album.composition import (
    HorizontalAlignment,
    PageComposer,
    PageComposition,
    PhotoSlotComposition,
)
from photoalbum.rendering.fonts import resolve_font_family

from photoalbum.gui.preview_image_cache import PreviewImageCache

from photoalbum.gui.preview_render_service import (
    PreviewRenderService,
)
from photoalbum.template_engine import (
    template_extension_registry,
)
from photoalbum.i18n import Translator
from photoalbum.rendering import (
    PageRenderer,
    RenderImageCache,
)



PREVIEW_PAGE_WIDTH = 300
PREVIEW_PAGE_MAX_WIDTH = 550


PreviewThumbnailCache = RenderImageCache


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

        self._page_ratio = ratio

        self.set_page_width(
            self.PAGE_WIDTH
        )

    def set_page_width(
        self,
        width: int,
    ) -> None:
        width = max(
            1,
            int(width),
        )

        self.setFixedSize(
            width,
            round(
                width * self._page_ratio
            ),
        )

        # Font sizes and all other print-scaled elements depend
        # on the current preview width. Repaint after resizing.
        self.update()

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
        self._paint_border(painter)

    def _paint_border(self, painter: QPainter) -> None:
        # Full-page template images can cover the initial paper outline.
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
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
        painter.restore()


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
        template_pack_settings=None,
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
        self._template_pack_settings = dict(
            template_pack_settings or {}
        )

        self._shared_preview_key = None

        self._render_service.preview_ready.connect(
            self._shared_preview_ready
        )

        self._render_service.preview_failed.connect(
            self._shared_preview_failed
        )


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
                template_pack_settings=(
                    self._template_pack_settings
                ),
            )
            self._paint_border(painter)
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

        font = QFont(
            resolve_font_family(None)
        )
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
        template_pack_settings=None,
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

        self._page_renderer = PageRenderer(
            translator=self._translator,
        )

        self._project_photos = tuple(
            project_photos or ()
        )

        self._album_pages = tuple(
            album_pages or ()
        )

        self._template_pack_settings = dict(
            template_pack_settings or {}
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

        try:
            self._paint_paper(
                painter
            )

            self._page_renderer.paint(
                painter=painter,
                composition=self._composition,
                target_rect=self.rect(),
                width=self.width(),
                height=self.height(),
                page_width_mm=(
                    self._page_format.width_mm
                ),
                page_height_mm=(
                    self._page_format.height_mm
                ),
                font_pixel_size=(
                    self._print_font_pixel_size
                ),
                pixel_rect=self._pixel_rect,
                thumbnail_cache=(
                    self._thumbnail_cache
                ),
                project_photos=(
                    self._project_photos
                ),
                album_pages=(
                    self._album_pages
                ),
                template_pack_settings=(
                    self._template_pack_settings
                ),
                render_service=(
                    self._render_service
                ),
                set_waiting_key=(
                    self._set_template_preview_key
                ),
                paint_fallback=(
                    self._paint_non_photo_page
                ),
            )
            self._paint_border(painter)
        finally:
            painter.end()

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

        font = QFont(
            resolve_font_family(None)
        )
        font.setBold(False)
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

        font = QFont(
            resolve_font_family(None)
        )
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
        self._thumbnail_cache = PreviewImageCache(self)
        self._page_widgets: list[_PreviewPageBase] = []

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._image_request_timer = QTimer(self)
        self._image_request_timer.setSingleShot(True)
        self._image_request_timer.timeout.connect(self._request_page_images)
        self._scroll.verticalScrollBar().valueChanged.connect(
            lambda: self._image_request_timer.start(0)
        )
        self._thumbnail_cache.ready.connect(self._image_ready)

        # The scroll viewport is the real source of the width
        # available to a two-page spread. Its geometry may change
        # without AlbumPreviewWidget itself receiving a resize.
        self._scroll.viewport().installEventFilter(
            self
        )

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
        self._image_request_timer.stop()
        self._clear_pages()
        self._thumbnail_cache.clear()

    def _clear_pages(self) -> None:
        while self._pages_grid.count():
            item = self._pages_grid.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self._page_widgets.clear()

    def _add_page_widget(
        self,
        widget: _PreviewPageBase,
        row: int,
        column: int,
    ) -> None:
        self._page_widgets.append(
            widget
        )

        self._pages_grid.addWidget(
            widget,
            row,
            column,
            Qt.AlignmentFlag.AlignTop,
        )

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
            template_pack_settings=(
                settings.template_pack_settings
            ),
        )

    def _image_ready(self, path: str) -> None:
        for page in self._page_widgets:
            if isinstance(page, AlbumPagePreview) and any(
                str(photo.path) == path for photo in page._composition.page.photos
            ):
                page.update()

    def event(self, event) -> bool:
        if (event.type() == QEvent.Type.DevicePixelRatioChange
                and hasattr(self, "_image_request_timer")):
            self._image_request_timer.start(0)
        return super().event(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._image_request_timer.start(0)

    def _request_page_images(self) -> None:
        pages = [p for p in self._page_widgets if isinstance(p, AlbumPagePreview)]
        if not pages:
            return
        maximum_height = max(PREVIEW_PAGE_MAX_WIDTH * p._page_ratio for p in pages)
        self._thumbnail_cache.set_resolution(
            PREVIEW_PAGE_MAX_WIDTH, maximum_height, self.devicePixelRatioF(),
        )
        top = self._scroll.verticalScrollBar().value()
        height = self._scroll.viewport().height()
        visible, nearby = [], []
        for page in pages:
            rect = page.geometry()
            if rect.bottom() >= top and rect.top() <= top + height:
                visible.append(page)
            elif rect.bottom() >= top - height and rect.top() <= top + 2 * height:
                nearby.append(page)
        # Hidden tabs may not yet have a usable layout: prepare the first pages.
        selected = visible + nearby if self.isVisible() else pages[:3]
        self._thumbnail_cache.prioritize(
            photo.path for page in selected
            for photo in page._composition.page.photos[:len(page._composition.photo_slots)]
        )

    def _resize_page_widgets(
        self,
    ) -> None:
        if not self._page_widgets:
            return

        viewport_width = (
            self._scroll.viewport().width()
        )

        margins = (
            self._pages_grid.contentsMargins()
        )

        available_width = (
            viewport_width
            - margins.left()
            - margins.right()
            - self.SPREAD_HORIZONTAL_GAP
            - 8
        )

        page_width = min(
            PREVIEW_PAGE_MAX_WIDTH,
            max(
                PREVIEW_PAGE_WIDTH,
                available_width // 2,
            ),
        )

        self._image_request_timer.start(0)
        for widget in self._page_widgets:
            if widget.width() == page_width:
                continue
            widget.set_page_width(
                page_width
            )

    def eventFilter(
        self,
        watched,
        event,
    ) -> bool:
        if (
            watched is self._scroll.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            # Let Qt finish the scroll-area layout first. In
            # particular this matters when the Preview tab becomes
            # visible for the first time.
            QTimer.singleShot(
                0,
                self._resize_page_widgets,
            )

        return super().eventFilter(
            watched,
            event,
        )

    def set_result(
        self,
        result: AlbumBuildResult,
        settings: AlbumStructureSettings,
        *,
        page_format: PageFormat | None = None,
    ) -> None:
        self._clear_pages()
        self._thumbnail_cache.invalidate_changed_sources()
        self._current_result = result

        if page_format is None:
            page_format = settings.effective_page_format()

        # Row 0: outer front cover, right side.
        self._add_page_widget(
            self._cover_widget(
                settings,
                CoverPosition.FRONT,
                page_format,
            ),
            0,
            1,
        )

        # Row 1: inside front cover on the left.
        self._add_page_widget(
            self._cover_widget(
                settings,
                CoverPosition.INSIDE_FRONT,
                page_format,
            ),
            1,
            0,
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
            reserved_caption_lines = (
                self._composer.spread_caption_lines(
                    page,
                    pages,
                    settings.photo_pages,
                    page_width_mm=page_format.width_mm,
                    page_height_mm=page_format.height_mm,
                )
            )

            composition = self._composer.compose(
                page,
                settings.photo_pages,
                settings.page_numbers,
                page_width_mm=page_format.width_mm,
                page_height_mm=page_format.height_mm,
                reserved_caption_lines=reserved_caption_lines,
            )

            preview = AlbumPagePreview(
                composition,
                thumbnail_cache=self._thumbnail_cache,
                page_format=page_format,
                translator=self._translator,
                render_service=self._render_service,
                project_photos=project_photos,
                album_pages=result.pagination.pages,
                template_pack_settings=(
                    settings.template_pack_settings
                ),
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

            self._add_page_widget(
                preview,
                row,
                column,
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
        self._add_page_widget(
            self._cover_widget(
                settings,
                CoverPosition.INSIDE_BACK,
                page_format,
            ),
            inside_back_row,
            1,
        )

        # Outside back cover is displayed alone on the left.
        self._add_page_widget(
            self._cover_widget(
                settings,
                CoverPosition.BACK,
                page_format,
            ),
            inside_back_row + 1,
            0,
        )

        # The viewport can still have its old geometry while the
        # preview tab is being populated. Resize once Qt has
        # completed the current layout pass.
        QTimer.singleShot(
            0,
            self._resize_page_widgets,
        )
