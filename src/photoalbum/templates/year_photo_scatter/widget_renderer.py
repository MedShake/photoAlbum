from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
)

from photoalbum.album import PageInstance

from .composition import compose_cover_scatter


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
    ) -> None:
        photos = tuple(
            photos
        )

        key = render_service.key_for(
            instance,
            photos,
            width=width,
            height=height,
        )

        set_waiting_key(
            key
        )

        pixmap = render_service.cached(
            key
        )

        if pixmap is None:
            render_service.request(
                instance,
                photos,
                width=width,
                height=height,
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

        effective_photos = (
            render_service.effective_photos(
                instance,
                photos,
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
        )

        font = QFont(
            painter.font()
        )

        font.setBold(
            True
        )

        font.setPixelSize(
            font_pixel_size(
                72
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

        painter.drawText(
            target_rect.adjusted(
                15,
                15,
                -15,
                -15,
            ),
            Qt.AlignmentFlag.AlignCenter,
            composition.title,
        )
