from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
)

from photoalbum.rendering.fonts import resolve_font_family

from photoalbum.album import PageInstance

from .composition import compose_cover_scatter
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

        font = QFont(
            resolve_font_family(None)
        )

        font.setBold(
            True
        )

        title = composition.title.strip()

        # Physical print sizes.
        #
        # The historical implementation used very large
        # screen-oriented values. Here the value is converted
        # by font_pixel_size(), so it must represent a real
        # typographic point size on paper.
        if (
            len(title) == 4
            and title.isdigit()
        ):
            title_font_pt = 72

        elif (
            len(title) == 9
            and title[4] in ("-", "–")
            and title[:4].isdigit()
            and title[5:].isdigit()
        ):
            title_font_pt = 52

        else:
            # Typically "Mois ANNEE".
            title_font_pt = 44

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
