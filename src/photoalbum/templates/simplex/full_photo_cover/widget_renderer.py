from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QImageReader, QPixmap

from .geometry import centered_cover_crop


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


renderer = SimplexFullPhotoCoverRenderer()
