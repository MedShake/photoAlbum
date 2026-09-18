from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFont,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
    PhotoCaptionSettings,
    PhotoPageSettings,
)
from photoalbum.album.composition import (
    build_photo_caption,
)
from photoalbum.i18n.date_formatter import (
    format_datetime,
)
from photoalbum.rendering.fonts import (
    resolve_font_family,
)
from photoalbum.templates.msb.settings_base import (
    MsbTemplateSettingsWidget,
)


class PhotoPageSettingsWidget(
    MsbTemplateSettingsWidget
):
    """Settings entry point shared by photo-page-1..4."""

    PREVIEW_WIDTH = 360
    PREVIEW_HEIGHT = 510

    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator,
        render_service=None,
        page_format: PageFormat = A4,
        template_pack_settings=None,
        parent=None,
    ) -> None:
        super().__init__(
            instance,
            photos,
            translator=translator,
            render_service=render_service,
            page_format=page_format,
            template_pack_settings=template_pack_settings,
            parent=parent,
        )

        root = QHBoxLayout(self)
        root.setSpacing(24)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        left_layout.addWidget(
            self.create_page_settings_title()
        )
        left_layout.addWidget(
            self.create_no_page_settings_label()
        )
        left_layout.addSpacing(12)
        left_layout.addWidget(
            self.create_msb_theme_group()
        )
        left_layout.addStretch()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        right_layout.addWidget(
            self.create_preview_title()
        )

        self._preview_label = QLabel()
        self._preview_label.setFixedSize(
            self.PREVIEW_WIDTH,
            self.PREVIEW_HEIGHT,
        )
        self._preview_label.setStyleSheet(
            "border: 1px solid #888;"
            "background: white;"
        )

        right_layout.addWidget(
            self._preview_label,
            alignment=Qt.AlignmentFlag.AlignTop,
        )
        right_layout.addStretch()

        root.addWidget(left, 1)
        root.addWidget(right, 0)

        self._render_preview()

    def msb_theme_changed(self) -> None:
        self._render_preview()

    def _render_preview(self) -> None:
        """
        Lightweight representative preview.

        The production PhotoPageWidgetRenderer deliberately
        requires a real PageComposition, thumbnail cache and
        pixel_rect. A settings editor has none of those, so it
        must not invent them.

        This preview therefore shows the selected template's
        number of photo zones and, when project photos are
        available, uses their actual image files.
        """
        pixmap = QPixmap(
            self.PREVIEW_WIDTH,
            self.PREVIEW_HEIGHT,
        )
        pixmap.fill(Qt.GlobalColor.white)

        painter = QPainter(pixmap)

        try:
            capacity = int(
                self._instance.template_id.rsplit(
                    "-",
                    1,
                )[1]
            )
        except (ValueError, IndexError):
            capacity = 1

        capacity = max(1, min(4, capacity))

        margin = 24
        gap = 12

        usable_width = (
            self.PREVIEW_WIDTH - 2 * margin
        )
        usable_height = (
            self.PREVIEW_HEIGHT - 2 * margin
        )

        if capacity == 1:
            rows, columns = 1, 1
        elif capacity == 2:
            rows, columns = 2, 1
        else:
            rows, columns = 2, 2

        cell_width = (
            usable_width
            - gap * (columns - 1)
        ) // columns

        cell_height = (
            usable_height
            - gap * (rows - 1)
        ) // rows

        # Même logique visuelle que les vraies pages :
        # une petite zone sous chaque photo est réservée
        # à la légende.
        caption_height = max(
            34,
            min(52, cell_height // 5),
        )
        image_height = max(
            1,
            cell_height - caption_height,
        )

        for index in range(capacity):
            row = index // columns
            column = index % columns

            x = margin + column * (
                cell_width + gap
            )
            y = margin + row * (
                cell_height + gap
            )

            image_rect = pixmap.rect().__class__(
                x,
                y,
                cell_width,
                image_height,
            )

            caption_rect = pixmap.rect().__class__(
                x,
                y + image_height,
                cell_width,
                caption_height,
            )

            drawn = False

            if index < len(self._photos):
                path = getattr(
                    self._photos[index],
                    "path",
                    None,
                )

                if path is not None:
                    photo = QPixmap(str(path))

                    if not photo.isNull():
                        scaled = photo.scaled(
                            image_rect.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )

                        px = (
                            image_rect.x()
                            + (
                                image_rect.width()
                                - scaled.width()
                            ) // 2
                        )
                        py = (
                            image_rect.y()
                            + (
                                image_rect.height()
                                - scaled.height()
                            ) // 2
                        )

                        painter.drawPixmap(
                            px,
                            py,
                            scaled,
                        )
                        drawn = True

            if not drawn:
                painter.setPen(
                    Qt.GlobalColor.lightGray
                )
                painter.drawRect(image_rect)
                painter.drawText(
                    image_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    str(index + 1),
                )

            if index < len(self._photos):
                caption = build_photo_caption(
                    self._photos[index],
                    PhotoPageSettings(
                        page=self._instance,
                        caption=PhotoCaptionSettings(
                            show_datetime=True,
                            show_location=True,
                        ),
                    ),
                )

                lines: list[str] = []
                first_line_parts: list[str] = []

                if caption.caption_text:
                    first_line_parts.append(
                        caption.caption_text
                    )

                if (
                    caption.capture_datetime
                    is not None
                ):
                    first_line_parts.append(
                        format_datetime(
                            caption.capture_datetime
                        )
                    )

                if first_line_parts:
                    lines.append(
                        " — ".join(
                            first_line_parts
                        )
                    )

                if caption.location_text:
                    lines.append(
                        caption.location_text
                    )

                if lines:
                    font = QFont(
                        resolve_font_family(None)
                    )
                    font.setBold(False)

                    # 8 pt environ à l'échelle de
                    # notre miniature.
                    font.setPixelSize(
                        max(
                            8,
                            round(
                                8
                                * self.PREVIEW_HEIGHT
                                / 510
                            ),
                        )
                    )

                    painter.setFont(font)
                    painter.setPen(
                        Qt.GlobalColor.black
                    )

                    painter.drawText(
                        caption_rect.adjusted(
                            3,
                            2,
                            -3,
                            -2,
                        ),
                        (
                            Qt.AlignmentFlag.AlignHCenter
                            | Qt.AlignmentFlag.AlignTop
                            | Qt.TextFlag.TextWordWrap
                        ),
                        "\n".join(lines),
                    )

        painter.end()
        self._preview_label.setPixmap(pixmap)
