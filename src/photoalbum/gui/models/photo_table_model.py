from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from photoalbum.geocoding.location_caption_builder import (
    LocationCaptionBuilder,
)
from photoalbum.i18n import Translator
from photoalbum.models import Photo


class PhotoTableModel(QAbstractTableModel):
    HEADER_KEYS = (
        "photos.column.filename",
        "photos.column.actions",
        "photos.column.capture_date",
        "photos.column.date_source",
        "photos.column.gps",
        "photos.column.city",
        "photos.column.location_source",
        "photos.column.status",
    )

    SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(
        self,
        photos: Sequence[Photo] | None = None,
        translator: Translator | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._translator = translator or Translator("en")
        self._photos = list(photos or [])
        self._location_caption_builder = LocationCaptionBuilder()

    def rowCount(
        self,
        parent: QModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0

        return len(self._photos)

    def columnCount(
        self,
        parent: QModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0

        return len(self.HEADER_KEYS)

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if not index.isValid():
            return None

        if not (
            0 <= index.row() < len(self._photos)
        ):
            return None

        photo = self._photos[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(
                photo,
                index.column(),
            )

        if role == Qt.ItemDataRole.ToolTipRole:
            if index.column() == 5:
                return self._location_tooltip(photo)

            return str(photo.path)

        if role == self.SORT_ROLE:
            return self._sort_value(
                photo,
                index.column(),
            )

        if role == Qt.ItemDataRole.UserRole:
            return photo

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation
            == Qt.Orientation.Horizontal
            and 0 <= section < len(self.HEADER_KEYS)
        ):
            return self._translator.tr(
                self.HEADER_KEYS[section]
            )

        return super().headerData(
            section,
            orientation,
            role,
        )

    def set_photos(
        self,
        photos: Sequence[Photo],
    ) -> None:
        self.beginResetModel()
        self._photos = list(photos)
        self.endResetModel()

    def clear(self) -> None:
        self.set_photos([])

    def photo_at(
        self,
        row: int,
    ) -> Photo | None:
        if not 0 <= row < len(self._photos):
            return None

        return self._photos[row]

    def _display_value(
        self,
        photo: Photo,
        column: int,
    ) -> str:
        if column == 0:
            return photo.filename

        # Column 1 contains action widgets installed by the view.
        if column == 1:
            return ""

        if column == 2:
            if photo.capture_datetime is None:
                return "—"

            return photo.capture_datetime.isoformat(
                sep=" ",
                timespec="seconds",
            )

        if column == 3:
            return self._translator.tr(
                f"photos.date_source.{photo.date_source.value}"
            )

        if column == 4:
            return self._translator.tr(
                "photos.value.yes"
                if photo.has_gps
                else "photos.value.no"
            )

        if column == 5:
            caption_result = self._location_caption_result(photo)

            if caption_result.caption:
                return caption_result.caption

            # Compatibility fallback for photos that have no preserved
            # reverse-geocoding response.
            return photo.place_name or photo.city or "—"

        if column == 6:
            return self._translator.tr(
                "photos.location_source."
                f"{photo.location_source.value}"
            )

        if column == 7:
            if photo.is_date_anomaly:
                return self._translator.tr(
                    "photos.value.missing_date"
                )

            return self._translator.tr(
                "photos.value.ok"
            )

        return ""

    def _location_tooltip(
        self,
        photo: Photo,
    ) -> str:
        lines = []

        caption_result = self._location_caption_result(photo)

        if caption_result.caption:
            lines.append(
                self._translator.tr(
                    "photos.location_tooltip.caption",
                    value=caption_result.caption,
                )
            )

        if caption_result.candidates:
            if lines:
                lines.append("")

            lines.append(
                self._translator.tr(
                    "photos.location_tooltip.available"
                )
            )

            selected_keys = {
                candidate.key
                for candidate in caption_result.selected
            }

            for candidate in caption_result.candidates:
                marker = (
                    "✓"
                    if candidate.key in selected_keys
                    else " "
                )

                lines.append(
                    f"{marker} {candidate.key}: "
                    f"{candidate.value}"
                )

        if photo.address:
            if lines:
                lines.append("")

            lines.append(
                self._translator.tr(
                    "photos.location_tooltip.address",
                    value=photo.address,
                )
            )

        if (
            photo.latitude is not None
            and photo.longitude is not None
        ):
            lines.append(
                self._translator.tr(
                    "photos.location_tooltip.gps",
                    latitude=f"{photo.latitude:.7f}",
                    longitude=f"{photo.longitude:.7f}",
                )
            )

        lines.append(
            self._translator.tr(
                "photos.location_tooltip.source",
                value=self._translator.tr(
                    "photos.location_source."
                    f"{photo.location_source.value}"
                ),
            )
        )

        return "\n".join(lines)

    def _location_caption_result(
        self,
        photo: Photo,
    ):
        return self._location_caption_builder.build(
            photo.raw_location_data
        )

    @staticmethod
    def _sort_value(
        photo: Photo,
        column: int,
    ):
        if column == 0:
            return photo.filename.lower()

        if column == 1:
            return 1 if photo.capture_datetime is None else 0

        if column == 2:
            if photo.capture_datetime is None:
                return ""

            return photo.capture_datetime.isoformat()

        if column == 3:
            return photo.date_source.value

        if column == 4:
            return 1 if photo.has_gps else 0

        if column == 5:
            return (photo.city or "").lower()

        if column == 6:
            return photo.location_source.value

        if column == 7:
            return 1 if photo.is_date_anomaly else 0

        return ""
