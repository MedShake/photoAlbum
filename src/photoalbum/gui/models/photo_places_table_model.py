from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)

from photoalbum.geocoding.location_caption_builder import (
    LocationCaptionBuilder,
)
from photoalbum.i18n import Translator
from photoalbum.models import LocationComponent, Photo


class PhotoPlacesTableModel(QAbstractTableModel):
    HEADER_KEYS = (
        "photos.places.column.number",
        "",
        "photos.places.column.photo",
        "photos.places.column.location",
        "photos.places.column.composition",
        "",
    )

    def __init__(
        self,
        photos: Sequence[Photo] | None = None,
        translator: Translator | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._translator = translator or Translator("en")
        self._photos = list(photos or [])
        self._photo_numbers = {
            id(photo): number
            for number, photo in enumerate(
                self._photos,
                start=1,
            )
        }
        self._caption_builder = LocationCaptionBuilder()

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

        if not 0 <= index.row() < len(self._photos):
            return None

        photo = self._photos[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(
                photo,
                index.row(),
                index.column(),
            )

        if role == Qt.ItemDataRole.ToolTipRole:
            if index.column() == 1:
                if photo.capture_datetime is None:
                    return "—"

                return photo.capture_datetime.strftime(
                    "%d/%m/%Y %H:%M:%S"
                )

            if index.column() == 2:
                return str(photo.path)

            if index.column() in (3, 4):
                return self._location_tooltip(photo)

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
            and orientation == Qt.Orientation.Horizontal
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
        self._photo_numbers = {
            id(photo): number
            for number, photo in enumerate(
                self._photos,
                start=1,
            )
        }
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
        row: int,
        column: int,
    ) -> str:
        if column == 0:
            return str(
                self._photo_numbers.get(
                    id(photo),
                    row + 1,
                )
            )

        # Compact chronological marker. The complete date is
        # available in the tooltip.
        if column == 1:
            return "◷" if photo.capture_datetime else "—"

        if column == 2:
            return f"👁  {photo.filename}"

        if column == 3:
            return self._location_text(photo)

        if column == 4:
            return ""

        # Column 5 contains the free-location editor installed
        # by the view.
        if column == 5:
            return ""

        return ""

    def sort(
        self,
        column: int,
        order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    ) -> None:
        if column not in (0, 1, 2, 3):
            return

        self.layoutAboutToBeChanged.emit()

        reverse = (
            order == Qt.SortOrder.DescendingOrder
        )

        if column == 1:
            # Keep undated photos after dated photos in both
            # directions while reversing only the dated group.
            dated = [
                photo
                for photo in self._photos
                if photo.capture_datetime is not None
            ]
            undated = [
                photo
                for photo in self._photos
                if photo.capture_datetime is None
            ]

            dated.sort(
                key=lambda photo: photo.capture_datetime,
                reverse=reverse,
            )

            self._photos = dated + undated
        else:
            self._photos.sort(
                key=lambda photo: self._sort_value(
                    photo,
                    column,
                ),
                reverse=reverse,
            )

        self.layoutChanged.emit()

    def _sort_value(
        self,
        photo: Photo,
        column: int,
    ):
        if column == 0:
            return self._photo_numbers.get(
                id(photo),
                0,
            )

        if column == 2:
            return photo.filename.casefold()

        if column == 3:
            return self._location_text(
                photo
            ).casefold()

        return ""

    def _location_text(
        self,
        photo: Photo,
    ) -> str:
        # Once the user has made an editorial choice, that choice
        # always wins over the automatic suggestion. An empty
        # selection is therefore a valid explicit choice.
        if photo.location_selection_edited:
            if photo.location_text:
                text = photo.location_text.strip()

                if text:
                    return text

            return "—"

        result = self._caption_builder.build(
            photo.raw_location_data
        )

        return result.caption or "—"

    def set_selected_components(
        self,
        row: int,
        components: tuple[LocationComponent, ...],
    ) -> str | None:
        photo = self.photo_at(row)

        if photo is None:
            return None

        location_text = ", ".join(
            component.value
            for component in components
        )

        photo.selected_location_components = components
        photo.location_text = location_text or None
        photo.location_selection_edited = True

        index = self.index(row, 3)
        self.dataChanged.emit(
            index,
            index,
            [Qt.ItemDataRole.DisplayRole],
        )

        return photo.location_text

    def set_location_text(
        self,
        row: int,
        location_text: str | None,
    ) -> str | None:
        photo = self.photo_at(row)

        if photo is None:
            return None

        if location_text is not None:
            location_text = location_text.strip()

        photo.location_text = location_text or None
        photo.location_selection_edited = True

        index = self.index(row, 3)
        self.dataChanged.emit(
            index,
            index,
            [Qt.ItemDataRole.DisplayRole],
        )

        return photo.location_text

    def caption_result_at(
        self,
        row: int,
    ):
        photo = self.photo_at(row)

        if photo is None:
            return None

        return self._caption_builder.build(
            photo.raw_location_data
        )

    def _location_tooltip(
        self,
        photo: Photo,
    ) -> str:
        result = self._caption_builder.build(
            photo.raw_location_data
        )

        lines = [
            self._translator.tr(
                "photos.places.tooltip.location",
                value=self._location_text(photo),
            )
        ]

        if result.candidates:
            lines.append("")

            for candidate in result.candidates:
                lines.append(
                    f"{candidate.key}: {candidate.value}"
                )

        return "\n".join(lines)
