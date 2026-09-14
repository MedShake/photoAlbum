from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from photoalbum.album import PlannedPage


class AlbumPageTableModel(QAbstractTableModel):
    HEADERS = (
        "Page",
        "Side",
        "Type",
        "Template",
        "Period",
        "Photos",
        "Unused slots",
        "Blank reason",
    )

    def __init__(
        self,
        pages: Sequence[PlannedPage] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._pages = list(pages or [])

    def rowCount(
        self,
        parent: QModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0

        return len(self._pages)

    def columnCount(
        self,
        parent: QModelIndex = QModelIndex(),
    ) -> int:
        if parent.isValid():
            return 0

        return len(self.HEADERS)

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if not index.isValid():
            return None

        if not 0 <= index.row() < len(self._pages):
            return None

        page = self._pages[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(
                page,
                index.column(),
            )

        if role == Qt.ItemDataRole.UserRole:
            return page

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
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]

        return super().headerData(
            section,
            orientation,
            role,
        )

    def set_pages(
        self,
        pages: Sequence[PlannedPage],
    ) -> None:
        self.beginResetModel()
        self._pages = list(pages)
        self.endResetModel()

    def clear(self) -> None:
        self.set_pages([])

    @staticmethod
    def _display_value(
        page: PlannedPage,
        column: int,
    ) -> str:
        if column == 0:
            return str(page.number)

        if column == 1:
            return page.side.value

        if column == 2:
            if page.kind is None:
                return "blank"

            return page.kind.value

        if column == 3:
            return page.template_id or "—"

        if column == 4:
            if page.year is None:
                return "—"

            if page.month is None:
                return str(page.year)

            return f"{page.year}-{page.month:02d}"

        if column == 5:
            return str(len(page.photos))

        if column == 6:
            if page.photo_capacity == 0:
                return "—"

            return str(page.unused_photo_slots)

        if column == 7:
            if page.blank_reason is None:
                return "—"

            return page.blank_reason.value

        return ""

