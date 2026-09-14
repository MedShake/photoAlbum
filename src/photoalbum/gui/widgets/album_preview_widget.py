from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
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
)

from photoalbum.album.composition import (
    HorizontalAlignment,
    PageComposer,
    PageComposition,
    PhotoSlotComposition,
)
from photoalbum.i18n import Translator


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

        self._scatter_cache_key = None
        self._scatter_cache_pixmap = QPixmap()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        self._paint_paper(painter)

        if self._template_id == "year-photo-scatter":
            self._paint_year_photo_scatter(
                painter
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

    def _project_photos(self):
        photos = []
        seen = set()

        for item in self._result.plan.items:
            for photo in item.photos:
                key = str(photo.path)

                if key in seen:
                    continue

                seen.add(key)
                photos.append(photo)

        return photos

    def _paint_year_photo_scatter(
        self,
        painter: QPainter,
    ) -> None:
        scatter = self._cover_settings.scatter

        photos = self._project_photos()

        composition = compose_cover_scatter(
            photos,
            seed=scatter.seed,
            photo_count=scatter.photo_count,
            month_name=self._translator.month_name,
        )

        cache_key = (
            composition.seed,
            composition.title,
            len(composition.items),
            self.width(),
            self.height(),
        )

        if (
            self._scatter_cache_key != cache_key
            or self._scatter_cache_pixmap.isNull()
        ):
            self._scatter_cache_pixmap = (
                self._render_scatter_pixmap(
                    composition
                )
            )

            self._scatter_cache_key = cache_key

        painter.drawPixmap(
            0,
            0,
            self._scatter_cache_pixmap,
        )

    def _render_scatter_pixmap(
        self,
        composition,
    ) -> QPixmap:
        image = QImage(
            self.size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )

        image.fill(
            Qt.GlobalColor.white
        )

        painter = QPainter(image)

        for item in composition.items:
            rect = self._pixel_rect(
                item.rect
            )

            pixmap = self._thumbnail_cache.load(
                item.photo.path,
                rect.size(),
            )

            if pixmap.isNull():
                continue

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

        font = QFont(painter.font())
        font.setBold(True)
        font.setPixelSize(
            self._print_font_pixel_size(72)
        )

        painter.setFont(font)
        painter.setPen(
            Qt.GlobalColor.white
        )

        painter.drawText(
            self.rect().adjusted(
                15,
                15,
                -15,
                -15,
            ),
            Qt.AlignmentFlag.AlignCenter,
            composition.title,
        )

        painter.end()

        return QPixmap.fromImage(image)


class AlbumPagePreview(_PreviewPageBase):
    def __init__(
        self,
        composition: PageComposition,
        *,
        thumbnail_cache: PreviewThumbnailCache,
        page_format: PageFormat = A4,
        translator: Translator | None = None,
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

    def paintEvent(
        self,
        event,
    ) -> None:
        painter = QPainter(self)

        self._paint_paper(painter)

        page = self._composition.page

        if page.kind == PlanItemKind.PHOTO_GROUP:
            self._paint_photo_page(
                painter
            )

        elif (
            page.kind
            == PlanItemKind.MONTH_DIVIDER
            and page.template_id
            == "month-divider-classic"
        ):
            self._paint_month_divider(
                painter
            )

        else:
            self._paint_non_photo_page(
                painter
            )

        self._paint_page_number(
            painter
        )

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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._registry = registry
        self._translator = translator or Translator("en")
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
