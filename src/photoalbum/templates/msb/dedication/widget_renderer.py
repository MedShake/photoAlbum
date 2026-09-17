from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QTextDocument,
)

from photoalbum.album import PageInstance
from photoalbum.rendering.fonts import (
    DEFAULT_SERIF_FONT,
    resolve_font_family,
)


class DedicationWidgetRenderer:
    DEFAULT_FRAME_COLOR = "#808080"
    DEFAULT_FRAME_WIDTH = 0.5
    DEFAULT_FONT_FAMILY = DEFAULT_SERIF_FONT
    DEFAULT_FONT_SIZE = 12.0

    @classmethod
    def _settings(
        cls,
        instance: PageInstance,
    ) -> dict:
        settings = instance.settings.get(
            "dedication",
            {},
        )

        if not isinstance(settings, dict):
            return {}

        return settings

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
) -> None:
        settings = self._settings(
            instance
        )

        text = str(
            settings.get(
                "text",
                "",
            )
        )

        color = QColor(
            str(
                settings.get(
                    "frame_color",
                    self.DEFAULT_FRAME_COLOR,
                )
            )
        )

        if not color.isValid():
            color = QColor(
                self.DEFAULT_FRAME_COLOR
            )

        try:
            frame_width = float(
                settings.get(
                    "frame_width",
                    self.DEFAULT_FRAME_WIDTH,
                )
            )
        except (TypeError, ValueError):
            frame_width = (
                self.DEFAULT_FRAME_WIDTH
            )

        font_family = resolve_font_family(
            str(
                settings.get(
                    "font_family",
                    self.DEFAULT_FONT_FAMILY,
                )
            ),
            fallback=self.DEFAULT_FONT_FAMILY,
        )

        try:
            font_size = float(
                settings.get(
                    "font_size",
                    self.DEFAULT_FONT_SIZE,
                )
            )
        except (TypeError, ValueError):
            font_size = (
                self.DEFAULT_FONT_SIZE
            )

        font_size = max(
            6.0,
            min(72.0, font_size),
        )

        sx = (
            target_rect.width()
            / page_width_mm
        )

        sy = (
            target_rect.height()
            / page_height_mm
        )

        # Cadre dans le tiers inférieur.
        margin_x_mm = 20.0
        margin_bottom_mm = 20.0
        frame_height_mm = (
            page_height_mm / 3.0
        )

        frame_rect = QRectF(
            target_rect.x()
            + margin_x_mm * sx,
            target_rect.y()
            + (
                page_height_mm
                - margin_bottom_mm
                - frame_height_mm
            ) * sy,
            (
                page_width_mm
                - 2.0 * margin_x_mm
            ) * sx,
            frame_height_mm * sy,
        )

        painter.save()

        pen = QPen(color)

        # Conversion points typographiques -> pixels.
        pixels_per_point = (
            sy * 25.4 / 72.0
        )

        pen.setWidthF(
            max(
                0.1,
                frame_width * pixels_per_point,
            )
        )

        painter.setPen(pen)
        painter.drawRect(frame_rect)

        # Zone de texte à l'intérieur du cadre.
        padding_mm = 8.0

        text_rect = frame_rect.adjusted(
            padding_mm * sx,
            padding_mm * sy,
            -padding_mm * sx,
            -padding_mm * sy,
        )

        if text.strip():
            document = QTextDocument()

            font = QFont(
                font_family
            )

            # QTextDocument travaille ici dans le même espace
            # graphique que le QPdfWriter / aperçu.
            #
            # On convertit donc explicitement les points
            # typographiques vers la taille en pixels du
            # périphérique de rendu.
            font.setPixelSize(
                max(
                    1,
                    font_pixel_size(
                        font_size
                    ),
                )
            )

            document.setDefaultFont(
                font
            )

            document.setMarkdown(text)
            document.setTextWidth(
                text_rect.width()
            )

            painter.translate(
                text_rect.topLeft()
            )

            document.drawContents(
                painter,
                QRectF(
                    0.0,
                    0.0,
                    text_rect.width(),
                    text_rect.height(),
                ),
            )

        painter.restore()
