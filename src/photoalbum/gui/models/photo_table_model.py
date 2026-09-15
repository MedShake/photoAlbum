from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

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
            return photo.city or "—"

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
