from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImageReader,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)

from .geometry import centered_cover_crop
from .title import (
    effective_title,
    title_color,
    title_font_family,
    title_font_size,
    title_position_index,
    title_visible,
)


PHOTO_PATH_KEY = "photo_path"
SOURCE_TYPE_KEY = "source_type"
EXTERNAL_PATH_KEY = "external_path"

SOURCE_PROJECT = "project"
SOURCE_EXTERNAL = "external"


def selected_photo(instance, photos):
    """
    Resolve the selected project photo.

    An explicit persisted path wins. For a fresh instance with no
    selection yet, the first project photo provides a useful default.
    """
    selected = instance.settings.get(PHOTO_PATH_KEY)

    if selected:
        selected = str(selected)

        for photo in photos:
            if str(photo.path) == selected:
                return photo

        # Do not silently change an explicit selection if the file
        # disappeared from the project.
        return None

    return photos[0] if photos else None


def selected_image_path(instance, photos):
    """
    Resolve the image used by the cover.

    Project mode resolves a Photo from the project. External mode
    directly references an image file outside the project.
    """
    source_type = str(
        instance.settings.get(
            SOURCE_TYPE_KEY,
            SOURCE_PROJECT,
        )
    )

    if source_type == SOURCE_EXTERNAL:
        path = str(
            instance.settings.get(
                EXTERNAL_PATH_KEY,
                "",
            )
        ).strip()

        return Path(path) if path else None

    photo = selected_photo(
        instance,
        photos,
    )

    if photo is None:
        return None

    return Path(photo.path)


class SimplexFullPhotoCoverRenderer:
    def paint(
        self,
        *,
        painter,
        instance,
        photos,
        target_rect,
        width,
        height,
        page_width_mm,
        page_height_mm,
        font_pixel_size,
        translator,
        render_service,
        album_pages,
        set_waiting_key,
        composition=None,
        pixel_rect=None,
        thumbnail_cache=None,
        **kwargs,
    ) -> None:
        path = selected_image_path(
            instance,
            photos,
        )

        if path is None:
            return

        reader = QImageReader(str(path))
        reader.setAutoTransform(True)

        source_size = reader.size()

        if not source_size.isValid():
            return

        # Decode only as large as useful for the current output while
        # preserving enough pixels for the cover crop.
        target_size = QSize(
            max(1, int(width)),
            max(1, int(height)),
        )

        scale = max(
            target_size.width() / source_size.width(),
            target_size.height() / source_size.height(),
        )

        decode_size = QSize(
            max(
                target_size.width(),
                round(source_size.width() * scale),
            ),
            max(
                target_size.height(),
                round(source_size.height() * scale),
            ),
        )

        reader.setScaledSize(decode_size)

        image = reader.read()

        if image.isNull():
            return

        pixmap = QPixmap.fromImage(image)

        crop = centered_cover_crop(
            pixmap.width(),
            pixmap.height(),
            target_rect.width(),
            target_rect.height(),
        )

        if crop is None:
            return

        destination = QRectF(target_rect)

        source = QRectF(
            crop.x,
            crop.y,
            crop.width,
            crop.height,
        )

        painter.save()

        try:
            painter.setClipRect(destination)
            painter.drawPixmap(
                destination,
                pixmap,
                source,
            )
        finally:
            painter.restore()

        if not title_visible(
            instance.settings
        ):
            return

        text = effective_title(
            instance.settings,
            photos,
            translator.month_name,
        )

        if not text.strip():
            return

        font = QFont(
            title_font_family(
                instance.settings
            )
        )
        font.setPointSizeF(
            title_font_size(
                instance.settings,
                text,
            )
        )

        custom = (
            str(
                instance.settings.get(
                    "title",
                    {},
                ).get(
                    "mode",
                    "automatic",
                )
            )
            == "custom"
        )

        if not custom:
            font.setBold(True)

        color = QColor(
            title_color(
                instance.settings
            )
        )

        horizontal_margin = (
            destination.width() * 0.06
        )
        vertical_margin = (
            destination.height() * 0.06
        )

        content_width = max(
            1.0,
            destination.width()
            - horizontal_margin * 2,
        )

        painter.save()

        try:
            if custom:
                document = QTextDocument()
                document.setDefaultFont(font)
                document.setDocumentMargin(0.0)
                document.setMarkdown(text)

                cursor = QTextCursor(document)
                cursor.select(
                    QTextCursor.SelectionType.Document
                )

                block_format = cursor.blockFormat()
                block_format.setAlignment(
                    Qt.AlignmentFlag.AlignHCenter
                )
                cursor.mergeBlockFormat(
                    block_format
                )

                char_format = QTextCharFormat()
                char_format.setForeground(color)
                cursor.mergeCharFormat(
                    char_format
                )

                document.setTextWidth(
                    content_width
                )

                title_height = min(
                    document.size().height(),
                    max(
                        1.0,
                        destination.height()
                        - vertical_margin * 2,
                    ),
                )
            else:
                painter.setFont(font)
                metrics = painter.fontMetrics()
                bounds = metrics.boundingRect(
                    QRect(
                        0,
                        0,
                        max(
                            1,
                            round(content_width),
                        ),
                        max(
                            1,
                            round(destination.height()),
                        ),
                    ),
                    int(
                        Qt.AlignmentFlag.AlignHCenter
                        | Qt.AlignmentFlag.AlignVCenter
                        | Qt.TextFlag.TextWordWrap
                    ),
                    text,
                )
                title_height = max(
                    1.0,
                    bounds.height(),
                )

            available_travel = max(
                0.0,
                destination.height()
                - vertical_margin * 2
                - title_height,
            )

            index = title_position_index(
                instance.settings
            )

            top = (
                destination.top()
                + vertical_margin
                + available_travel
                * index
                / 6.0
            )

            title_rect = QRectF(
                destination.left()
                + horizontal_margin,
                top,
                content_width,
                title_height,
            )

            if custom:
                painter.translate(
                    title_rect.topLeft()
                )
                document.drawContents(
                    painter,
                    QRectF(
                        0.0,
                        0.0,
                        title_rect.width(),
                        title_rect.height(),
                    ),
                )
            else:
                painter.setPen(color)
                painter.drawText(
                    title_rect,
                    int(
                        Qt.AlignmentFlag.AlignHCenter
                        | Qt.AlignmentFlag.AlignVCenter
                        | Qt.TextFlag.TextWordWrap
                    ),
                    text,
                )
        finally:
            painter.restore()


renderer = SimplexFullPhotoCoverRenderer()
