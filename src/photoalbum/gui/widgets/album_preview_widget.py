from __future__ import annotations


from bisect import bisect_right

from PySide6.QtCore import (
    QEvent,
    QRect,
    QTimer,
    Qt,
)
from PySide6.QtGui import (
    QFont,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
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
    PageComposer,
    PageComposition,
)
from photoalbum.rendering.fonts import resolve_font_family

from photoalbum.gui.preview_image_cache import PreviewImageCache
from photoalbum.gui.widgets.preview_navigation_ruler import (
    NavigationPage,
    PreviewNavigationRuler,
)

from photoalbum.gui.preview_render_service import (
    PreviewRenderService,
)
from photoalbum.gui.template_labels import template_display_name
from photoalbum.i18n import Translator
from photoalbum.rendering import (
    PageRenderer,
    RenderImageCache,
)



PREVIEW_PAGE_WIDTH = 300
PREVIEW_PAGE_MAX_WIDTH = 550
PREVIEW_LANDSCAPE_PAGE_MAX_WIDTH = 750
# Each lateral ruler consumes this width; both stay outside the QScrollArea.
PREVIEW_NAVIGATION_RESERVE = PreviewNavigationRuler.WIDTH


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
        self._shared_preview_key = None

        self.set_page_width(
            self.PAGE_WIDTH
        )

    @property
    def _maximum_page_width(self) -> int:
        return (
            PREVIEW_LANDSCAPE_PAGE_MAX_WIDTH
            if self._page_ratio < 1.0 else PREVIEW_PAGE_MAX_WIDTH
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

    def _set_template_preview_key(self, key) -> None:
        self._shared_preview_key = key

    def _shared_preview_ready(self, key) -> None:
        if key == self._shared_preview_key:
            self.update()

    def _shared_preview_failed(self, key, message: str) -> None:
        if key == self._shared_preview_key:
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
        self._page_composer = PageComposer()
        self._thumbnail_cache = thumbnail_cache
        self._translator = translator
        self._render_service = render_service
        self._template_pack_settings = dict(
            template_pack_settings or {}
        )

        self._render_service.preview_ready.connect(
            self._shared_preview_ready
        )

        self._render_service.preview_failed.connect(
            self._shared_preview_failed
        )


    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        self._paint_paper(painter)

        rendered = PageRenderer(translator=self._translator).paint_template(
            instance=self._cover_settings.page, painter=painter,
            composition=self._page_composer.compose_instance(
                self._cover_settings.page, self._project_photos(),
                page_width_mm=self._page_format.width_mm,
                page_height_mm=self._page_format.height_mm,
            ),
            photos=self._project_photos(), project_photos=self._project_photos(),
            target_rect=self.rect(), width=self.width(), height=self.height(),
            page_width_mm=self._page_format.width_mm,
            page_height_mm=self._page_format.height_mm,
            font_pixel_size=self._print_font_pixel_size, pixel_rect=self._pixel_rect,
            thumbnail_cache=self._thumbnail_cache, album_pages=self._result.pagination.pages,
            template_pack_settings=self._template_pack_settings,
            render_service=self._render_service, set_waiting_key=self._set_template_preview_key,
        )
        if rendered:
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

        template_name = template_display_name(
            template,
            self._translator,
        )

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

    def _project_photos(
        self,
    ):
        return list(self._result.template_photos)




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
        self._thumbnail_cache.ready.connect(self._thumbnail_ready)
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

        self._render_service = render_service

        if self._render_service is not None:
            self._render_service.preview_ready.connect(
                self._shared_preview_ready
            )
            self._render_service.preview_failed.connect(
                self._shared_preview_failed
            )


    def _thumbnail_ready(self, path: str) -> None:
        if any(str(photo.path) == path for photo in self._composition.page.photos):
            self.update()

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

    def _paint_non_photo_page(
        self,
        painter: QPainter,
    ) -> None:
        page = self._composition.page

        if page.blank_reason is not None:
            text = self._translator.tr(
                "preview.blank_page"
            )

        elif page.kind == PlanItemKind.DAY_DIVIDER:
            text = self._translator.tr("preview.day_divider")

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
        self._navigation_widgets: list[_PreviewPageBase] = []
        self._navigation_tops: list[int] = []
        self._navigation_first_indices: list[int] = []

        self._scroll = QScrollArea()
        self._scroll.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        self._image_request_timer = QTimer(self)
        self._image_request_timer.setSingleShot(True)
        self._image_request_timer.timeout.connect(self._request_page_images)
        self._scroll.verticalScrollBar().valueChanged.connect(
            self._scroll_position_changed
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

        self._pages_grid.setHorizontalSpacing(
            self.SPREAD_HORIZONTAL_GAP
        )

        self._pages_grid.setVerticalSpacing(
            self.SPREAD_VERTICAL_GAP
        )

        self._scroll.setWidget(
            self._content
        )

        self._date_ruler = PreviewNavigationRuler(
            self._translator, self, mode="date",
        )
        self._page_ruler = PreviewNavigationRuler(
            self._translator, self, mode="page",
        )
        self._date_ruler.page_activated.connect(self._navigate_to_page)
        self._page_ruler.page_activated.connect(self._navigate_to_page)
        self._date_ruler.page_explored.connect(self._explore_rulers)
        self._page_ruler.page_explored.connect(self._explore_rulers)
        layout = QHBoxLayout(self)
        layout.addWidget(self._date_ruler)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._page_ruler)

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
        self._content.resize(0, 0)
        self._navigation_widgets.clear()
        self._navigation_tops.clear()
        self._navigation_first_indices.clear()
        self._date_ruler.set_pages(())
        self._page_ruler.set_pages(())

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

    def create_cover_preview(
        self,
        settings: AlbumStructureSettings,
        position: CoverPosition,
        *,
        page_format: PageFormat | None = None,
        page_width: int | None = None,
        parent: QWidget | None = None,
    ) -> AlbumCoverPreview:
        """Create a cover preview through the exact same path as the Preview tab.

        This is intentionally public so other UI surfaces (notably Plan hover
        previews) can reuse the Preview tab's composer, render service and image
        cache instead of building a parallel rendering path.
        """
        if page_format is None:
            page_format = settings.effective_page_format()

        cover = settings.covers[position]
        preview = AlbumCoverPreview(
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
            parent=parent,
        )
        if page_width is not None:
            preview.set_page_width(page_width)
        return preview

    def _cover_widget(
        self,
        settings: AlbumStructureSettings,
        position: CoverPosition,
        page_format: PageFormat,
    ) -> AlbumCoverPreview:
        return self.create_cover_preview(
            settings,
            position,
            page_format=page_format,
        )

    def create_page_preview(
        self,
        page,
        settings: AlbumStructureSettings,
        *,
        page_format: PageFormat | None = None,
        page_width: int | None = None,
        parent: QWidget | None = None,
        prioritize_images: bool = False,
    ) -> AlbumPagePreview:
        """Create an interior-page preview using the Preview tab machinery."""
        if page_format is None:
            page_format = settings.effective_page_format()

        pages = self._current_result.pagination.pages
        reserved_caption_lines = self._composer.spread_caption_lines(
            page,
            pages,
            settings.photo_pages,
            page_width_mm=page_format.width_mm,
            page_height_mm=page_format.height_mm,
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
            project_photos=list(self._current_result.template_photos),
            album_pages=pages,
            template_pack_settings=settings.template_pack_settings,
            parent=parent,
        )
        if page_width is not None:
            preview.set_page_width(page_width)
        if prioritize_images:
            self.prioritize_preview_images(preview)
        return preview

    def prioritize_preview_images(self, preview: AlbumPagePreview) -> None:
        """Prioritize one page in the Preview tab's shared image cache."""
        self._thumbnail_cache.set_resolution(
            preview._maximum_page_width,
            round(preview._maximum_page_width * preview._page_ratio),
            preview.devicePixelRatioF(),
        )
        self._thumbnail_cache.prioritize(
            photo.path
            for photo in preview._composition.page.photos[
                :len(preview._composition.photo_slots)
            ]
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
        # Decode once at the largest useful preview size for this page format.
        # Window resizing only scales the cached image when painting.
        self._thumbnail_cache.set_resolution(
            max(p._maximum_page_width for p in pages),
            max(round(p._maximum_page_width * p._page_ratio) for p in pages),
            self.devicePixelRatioF(),
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

    @staticmethod
    def _navigation_page(page, translator: Translator) -> NavigationPage:
        """Use actual dated photos; special pages keep their period metadata."""
        dates = sorted({
            photo.capture_datetime.date()
            for photo in page.photos
            if photo.capture_datetime is not None
        })
        is_special = page.kind in {
            PlanItemKind.SPECIAL_PAGE, PlanItemKind.BODY_SPECIAL_PAGE,
        }
        number = page.number
        def formatted_date(value) -> str:
            return f"{value.day:02d} {translator.month_name(value.month)} {value.year}"

        short = "sp." if is_special else str(number)
        full = (f"{translator.tr('preview.special_page')} — {number}"
                if is_special else "")
        if dates:
            first, last = dates[0], dates[-1]
            label = formatted_date(first)
            if first != last:
                label += " – " + formatted_date(last)
            return NavigationPage(
                label, first.year, first.month, first.day,
                {PlanItemKind.YEAR_DIVIDER: "year",
                 PlanItemKind.MONTH_DIVIDER: "month",
                 PlanItemKind.DAY_DIVIDER: "day"}.get(page.kind),
                tuple((day.year, day.month, day.day) for day in dates),
                short, full, number,
            )
        if page.year is not None:
            if page.month is not None and page.day is not None:
                label = f"{page.day:02d} {translator.month_name(page.month)} {page.year}"
            elif page.month is not None:
                label = f"{translator.month_name(page.month)} {page.year}"
            else:
                label = str(page.year)
            return NavigationPage(
                label, page.year, page.month, page.day,
                {PlanItemKind.YEAR_DIVIDER: "year",
                 PlanItemKind.MONTH_DIVIDER: "month",
                 PlanItemKind.DAY_DIVIDER: "day"}.get(page.kind),
                (), short, full, number,
            )
        return NavigationPage("", short_label=short, page_label=full,
                              page_number=number)

    def _navigation_cover(self, position: CoverPosition) -> NavigationPage:
        names = {
            CoverPosition.FRONT: "front",
            CoverPosition.INSIDE_FRONT: "inside_front",
            CoverPosition.INSIDE_BACK: "inside_back",
            CoverPosition.BACK: "back",
        }
        name = names[position]
        return NavigationPage(
            "", short_label=self._translator.tr(f"preview.navigation.short.{name}"),
            page_label=self._translator.tr(f"preview.cover.{name}"),
        )

    def _refresh_navigation_positions(self) -> None:
        """Index spread offsets once after layout, not on each scroll event."""
        if not self._navigation_widgets:
            return
        self._pages_grid.activate()
        entries = sorted(
            (widget.y(), index) for index, widget in enumerate(self._navigation_widgets)
        )
        self._navigation_tops = []
        self._navigation_first_indices = []
        for top, index in entries:
            if self._navigation_tops and self._navigation_tops[-1] == top:
                self._navigation_first_indices[-1] = min(
                    self._navigation_first_indices[-1], index
                )
            else:
                self._navigation_tops.append(top)
                self._navigation_first_indices.append(index)
        self._sync_ruler_to_scroll()

    def _scroll_position_changed(self, _value: int) -> None:
        self._image_request_timer.start(0)
        self._sync_ruler_to_scroll()

    def _sync_ruler_to_scroll(self) -> None:
        if not self._navigation_tops:
            return
        top = self._scroll.verticalScrollBar().value()
        spread = max(0, bisect_right(self._navigation_tops, top + 2) - 1)
        for ruler in (self._date_ruler, self._page_ruler):
            # Preview scrolling takes ownership of both positions again.
            ruler.clear_exploration()
            ruler.set_current_index(self._navigation_first_indices[spread])

    def _explore_rulers(self, index: int, date_entry: int) -> None:
        """Keep both rulers together, without moving the scroll area."""
        if not 0 <= index < len(self._navigation_widgets):
            return
        self._date_ruler.set_explored_index(index, date_entry=date_entry)
        self._page_ruler.set_explored_index(index)

    def _navigate_to_page(self, index: int) -> None:
        if not 0 <= index < len(self._navigation_widgets):
            return
        # Both pages in a spread share the same scroll offset.  The ruler
        # nevertheless keeps the exact page targeted by the user selected.
        target = self._navigation_widgets[index]
        self._scroll.verticalScrollBar().setValue(target.y())
        for ruler in (self._date_ruler, self._page_ruler):
            ruler.clear_exploration()
            ruler.set_current_index(index)

    def _resize_page_widgets(
        self,
        viewport_width: int | None = None,
    ) -> None:
        if not self._page_widgets:
            return

        if viewport_width is None:
            viewport_width = self._scroll.viewport().width()

        margins = self._pages_grid.contentsMargins()
        available_width = (
            viewport_width
            - margins.left()
            - margins.right()
            - self.SPREAD_HORIZONTAL_GAP
            - 8
        )

        # The album has one common page format. A landscape spread can use
        # more horizontal room than a portrait spread without changing PDF
        # geometry or requiring horizontal scrolling.
        maximum_width = self._page_widgets[0]._maximum_page_width
        page_width = min(maximum_width, max(1, available_width // 2))

        self._image_request_timer.start(0)
        for widget in self._page_widgets:
            if widget.width() == page_width:
                continue
            widget.set_page_width(page_width)

        # Qt caps layout size hints around 524287 pixels. Letting the scroll
        # area or an aligned grid use that hint compresses tall albums' gaps.
        # Size the content from actual rows; the scroll area owns centering.
        row_heights: dict[int, int] = {}
        for index in range(self._pages_grid.count()):
            row = self._pages_grid.getItemPosition(index)[0]
            page = self._pages_grid.itemAt(index).widget()
            row_heights[row] = max(row_heights.get(row, 0), page.height())
        self._content.resize(
            2 * page_width + self.SPREAD_HORIZONTAL_GAP + margins.left() + margins.right(),
            sum(row_heights.values())
            + (len(row_heights) - 1) * self.SPREAD_VERTICAL_GAP
            + margins.top() + margins.bottom(),
        )
        QTimer.singleShot(0, self._refresh_navigation_positions)

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

        navigation_pages: list[NavigationPage] = []

        # Covers are physical pages too: they must be reachable via the
        # lower cyclic list, including both inside covers.
        front = self._cover_widget(settings, CoverPosition.FRONT, page_format)
        self._add_page_widget(front, 0, 1)
        self._navigation_widgets.append(front)
        navigation_pages.append(self._navigation_cover(CoverPosition.FRONT))

        inside_front = self._cover_widget(
            settings, CoverPosition.INSIDE_FRONT, page_format,
        )
        self._add_page_widget(inside_front, 1, 0)
        self._navigation_widgets.append(inside_front)
        navigation_pages.append(self._navigation_cover(CoverPosition.INSIDE_FRONT))

        pages = result.pagination.pages

        # Interior starts on the right opposite the inside
        # front cover. The factory is also used by Plan hover previews, so
        # composition/render/cache behavior cannot drift between the two UIs.
        for page in pages:
            preview = self.create_page_preview(
                page,
                settings,
                page_format=page_format,
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
            self._navigation_widgets.append(preview)
            navigation_pages.append(self._navigation_page(page, self._translator))

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

        inside_back = self._cover_widget(
            settings, CoverPosition.INSIDE_BACK, page_format,
        )
        self._add_page_widget(inside_back, inside_back_row, 1)
        self._navigation_widgets.append(inside_back)
        navigation_pages.append(self._navigation_cover(CoverPosition.INSIDE_BACK))

        back = self._cover_widget(settings, CoverPosition.BACK, page_format)
        self._add_page_widget(back, inside_back_row + 1, 0)
        self._navigation_widgets.append(back)
        navigation_pages.append(self._navigation_cover(CoverPosition.BACK))

        dividers = tuple(
            level for enabled, level in (
                (settings.year_dividers.enabled, "year"),
                (settings.month_dividers.enabled, "month"),
                (settings.day_dividers.enabled, "day"),
            ) if enabled
        )
        self._date_ruler.set_pages(navigation_pages, enabled_dividers=dividers)
        self._page_ruler.set_pages(navigation_pages, enabled_dividers=dividers)

        # The viewport can still have its old geometry while the
        # preview tab is being populated. Resize once Qt has
        # completed the current layout pass.
        QTimer.singleShot(
            0,
            self._resize_page_widgets,
        )
