from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget


class FlowLayout(QLayout):
    """Layout horizontal avec retour automatique à la ligne."""

    def __init__(
        self,
        parent: QWidget | None = None,
        margin: int = 0,
        horizontal_spacing: int = 8,
        vertical_spacing: int = 4,
    ) -> None:
        super().__init__(parent)

        self._items: list[QLayoutItem] = []
        self._hspace = horizontal_spacing
        self._vspace = vertical_spacing

        self.setContentsMargins(
            margin,
            margin,
            margin,
            margin,
        )

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]

        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)

        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(
            QRect(0, 0, width, 0),
            test_only=True,
        )

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()

        for item in self._items:
            size = size.expandedTo(
                item.minimumSize()
            )

        margins = self.contentsMargins()

        size += QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )

        return size

    def _do_layout(
        self,
        rect: QRect,
        *,
        test_only: bool,
    ) -> int:
        margins = self.contentsMargins()

        effective = rect.adjusted(
            margins.left(),
            margins.top(),
            -margins.right(),
            -margins.bottom(),
        )

        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()

            next_x = x + hint.width() + self._hspace

            if (
                x > effective.x()
                and next_x - self._hspace
                > effective.right() + 1
            ):
                x = effective.x()
                y += line_height + self._vspace
                next_x = x + hint.width() + self._hspace
                line_height = 0

            if not test_only:
                item.setGeometry(
                    QRect(
                        QPoint(x, y),
                        hint,
                    )
                )

            x = next_x
            line_height = max(
                line_height,
                hint.height(),
            )

        return (
            y
            + line_height
            - rect.y()
            + margins.bottom()
        )
