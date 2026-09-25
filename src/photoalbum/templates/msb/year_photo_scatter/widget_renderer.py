from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QColor,
    QFont,
    QPainter,
)


from photoalbum.album import PageInstance

from .composition import compose_cover_scatter
from .title_style import (
    title_font_family,
    title_font_size,
)
from .scatter_renderer import YearPhotoScatterRenderer


class YearPhotoScatterWidgetRenderer:
    """
    Paint the year-photo-scatter template inside any album
    preview page.

    It works identically for:
    - covers
    - special pages

    The host widget only provides generic rendering services.
    """

    DEFAULT_TITLE_COLOR = "#d0d0d0"

    @staticmethod
    def _scatter_settings(
        instance: PageInstance,
    ) -> dict:
        value = instance.settings.get(
            "scatter",
            {},
        )

        if isinstance(value, dict):
            return value

        return {}

    def _seed(
        self,
        instance: PageInstance,
    ) -> int:
        settings = self._scatter_settings(
            instance
        )

        seeds = settings.get(
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
            settings.get(
                "selected_seed_index",
                0,
            )
        )

        index = min(
            max(index, 0),
            len(seeds) - 1,
        )

        return seeds[index]

    def _title_mode(
        self,
        instance: PageInstance,
    ) -> str:
        mode = str(
            self._scatter_settings(
                instance
            ).get(
                "title_mode",
                "automatic",
            )
        )
        return (
            mode
            if mode in {
                "automatic",
                "custom",
            }
            else "automatic"
        )

    def _title_text(
        self,
        instance: PageInstance,
        automatic_title: str,
    ) -> str:
        if self._title_mode(instance) != "custom":
            return automatic_title

        return str(
            self._scatter_settings(
                instance
            ).get(
                "title_text",
                "",
            )
        )

    def _title_visible(
        self,
        instance: PageInstance,
    ) -> bool:
        settings = self._scatter_settings(
            instance
        )
        return bool(
            settings.get(
                "title_visible",
                True,
            )
        )

    def _title_position_index(
        self,
        instance: PageInstance,
    ) -> int:
        settings = self._scatter_settings(
            instance
        )
        position = str(
            settings.get(
                "title_position",
                "center",
            )
        )

        return {
            "very_high": 0,
            "high": 1,
            "upper_middle": 2,
            "center": 3,
            "lower_middle": 4,
            "low": 5,
            "very_low": 6,
        }.get(
            position,
            3,
        )

    def _title_color(
        self,
        instance: PageInstance,
    ) -> QColor:
        settings = self._scatter_settings(
            instance
        )

        color = QColor(
            str(
                settings.get(
                    "title_color",
                    self.DEFAULT_TITLE_COLOR,
                )
            )
        )

        if not color.isValid():
            return QColor(
                self.DEFAULT_TITLE_COLOR
            )

        return color

    def paint(
        self,
        *,
        painter: QPainter,
        instance: PageInstance,
        photos,
        target_rect,
        width: int,
        height: int,
        translator,
        render_service,
        set_waiting_key,
        font_pixel_size,
        page_width_mm: float = 210.0,
        page_height_mm: float = 297.0,
        album_pages=(),
        composition=None,
        thumbnail_cache=None,
        pixel_rect=None,
            template_pack_settings=None,
        **kwargs,
    ) -> None:
        photos = tuple(
            photos
        )

        if render_service is not None:
            effective_photos = (
                render_service.effective_photos(
                    instance,
                    photos,
                )
            )

            key = render_service.key_for(
                instance,
                effective_photos,
                width=width,
                height=height,
                page_width_mm=page_width_mm,
                page_height_mm=page_height_mm,
            )

            if set_waiting_key is not None:
                set_waiting_key(
                    key
                )

            pixmap = render_service.cached(
                key
            )

            if pixmap is None:
                render_service.request(
                    instance,
                    effective_photos,
                    width=width,
                    height=height,
                    page_width_mm=page_width_mm,
                    page_height_mm=page_height_mm,
                )

                painter.setPen(
                    Qt.GlobalColor.darkGray
                )

                painter.drawText(
                    target_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    translator.tr(
                        "page_settings.calculating"
                    ),
                )

                return

            painter.drawPixmap(
                target_rect,
                pixmap,
                pixmap.rect(),
            )

        else:
            # Synchronous path used by final rendering.
            #
            # The business rule remains owned by this template:
            # only dated photos participate in the scatter.
            unique = {}

            for photo in photos:
                if photo.capture_datetime is None:
                    continue

                unique.setdefault(
                    str(photo.path),
                    photo,
                )

            effective_photos = tuple(
                sorted(
                    unique.values(),
                    key=lambda photo: str(
                        photo.path
                    ),
                )
            )

        composition = compose_cover_scatter(
            list(
                effective_photos
            ),
            seed=self._seed(
                instance
            ),
            month_name=(
                translator.month_name
            ),
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
        )

        if render_service is None:
            if thumbnail_cache is None:
                raise RuntimeError(
                    "Scatter rendering requires an image cache."
                )

            YearPhotoScatterRenderer().paint(
                painter=painter,
                composition=composition,
                target_rect=target_rect,
                image_cache=thumbnail_cache,
            )

        if self._title_visible(
            instance
        ):
            title_text = self._title_text(
                instance,
                composition.title,
            )
            custom_title = (
                self._title_mode(instance)
                == "custom"
            )

            font = QFont(
                title_font_family(
                    instance.settings
                )
            )

            font.setBold(
                not custom_title
            )

            title_font_pt = title_font_size(
                instance.settings,
                title_text,
            )

            font.setPixelSize(
                font_pixel_size(
                    title_font_pt
                )
            )

            painter.setFont(
                font
            )

            painter.setPen(
                self._title_color(
                    instance
                )
            )

            title_rect = target_rect.adjusted(
                15,
                15,
                -15,
                -15,
            )

            if custom_title:
                document = QTextDocument()
                document.setDefaultFont(font)
                document.setDocumentMargin(0.0)
                document.setMarkdown(title_text)

                cursor = QTextCursor(document)
                cursor.select(
                    QTextCursor.SelectionType.Document
                )

                block_format = cursor.blockFormat()
                block_format.setAlignment(
                    Qt.AlignmentFlag.AlignHCenter
                )
                cursor.mergeBlockFormat(block_format)

                char_format = QTextCharFormat()
                char_format.setForeground(
                    self._title_color(instance)
                )
                cursor.mergeCharFormat(char_format)

                document.setTextWidth(
                    title_rect.width()
                )

                text_height = max(
                    1,
                    int(
                        document.size().height()
                    ),
                )
            else:
                metrics = painter.fontMetrics()
                text_height = max(
                    1,
                    metrics.boundingRect(
                        title_text
                    ).height(),
                )

            available_travel = max(
                0,
                title_rect.height()
                - text_height,
            )

            position_index = (
                self._title_position_index(
                    instance
                )
            )

            title_top = (
                title_rect.top()
                + round(
                    available_travel
                    * position_index
                    / 6
                )
            )

            positioned_title_rect = (
                title_rect.adjusted(
                    0,
                    title_top - title_rect.top(),
                    0,
                    -(
                        title_rect.bottom()
                        - title_top
                        - text_height
                        + 1
                    ),
                )
            )

            if custom_title:
                painter.save()
                painter.translate(
                    positioned_title_rect.topLeft()
                )
                document.drawContents(
                    painter,
                    QRectF(
                        0.0,
                        0.0,
                        positioned_title_rect.width(),
                        positioned_title_rect.height(),
                    ),
                )
                painter.restore()
            else:
                painter.drawText(
                    positioned_title_rect,
                    (
                        Qt.AlignmentFlag.AlignHCenter
                        | Qt.AlignmentFlag.AlignVCenter
                    ),
                    title_text,
                )
