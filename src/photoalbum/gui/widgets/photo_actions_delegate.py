from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
)

from photoalbum.models import Photo


class PhotoActionsDelegate(QStyledItemDelegate):
    """
    Paint and handle the actions available for a photo row.

    The delegate deliberately avoids index widgets so actions
    continue to follow the correct photo when the proxy model
    is sorted.
    """

    edit_datetime_requested = Signal(object)
    open_photo_requested = Signal(object)

    ICON_SIZE = 20
    BUTTON_SIZE = 30
    SPACING = 4

    def sizeHint(
        self,
        option,
        index,
    ) -> QSize:
        size = super().sizeHint(
            option,
            index,
        )

        return QSize(
            2 * self.BUTTON_SIZE + self.SPACING,
            max(
                size.height(),
                self.BUTTON_SIZE,
            ),
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        # Keep normal selection/background rendering.
        base_option = QStyleOptionViewItem(option)
        base_option.text = ""

        QApplication.style().drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            base_option,
            painter,
        )

        photo = index.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(photo, Photo):
            return

        date_rect, open_rect = self._action_rects(
            option.rect
        )

        self._paint_calendar(
            painter,
            date_rect,
            missing=(
                photo.capture_datetime is None
            ),
        )

        self._paint_open(
            painter,
            open_rect,
        )

    def editorEvent(
        self,
        event,
        model,
        option,
        index,
    ) -> bool:
        if (
            event.type()
            != QEvent.Type.MouseButtonRelease
            or not isinstance(event, QMouseEvent)
            or event.button()
            != Qt.MouseButton.LeftButton
        ):
            return super().editorEvent(
                event,
                model,
                option,
                index,
            )

        photo = index.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(photo, Photo):
            return False

        date_rect, open_rect = self._action_rects(
            option.rect
        )

        position = event.position().toPoint()

        if date_rect.contains(position):
            self.edit_datetime_requested.emit(
                photo
            )
            return True

        if open_rect.contains(position):
            self.open_photo_requested.emit(
                photo
            )
            return True

        return False

    def helpEvent(
        self,
        event,
        view,
        option,
        index,
    ) -> bool:
        photo = index.data(
            Qt.ItemDataRole.UserRole
        )

        if not isinstance(photo, Photo):
            return super().helpEvent(
                event,
                view,
                option,
                index,
            )

        date_rect, open_rect = self._action_rects(
            option.rect
        )

        position = event.pos()

        if date_rect.contains(position):
            QToolTip.showText(
                event.globalPos(),
                self.tr(
                    "Modifier la date de prise de vue"
                ),
                view,
            )
            return True

        if open_rect.contains(position):
            QToolTip.showText(
                event.globalPos(),
                self.tr(
                    "Voir la photo"
                ),
                view,
            )
            return True

        QToolTip.hideText()
        return False

    @classmethod
    def _action_rects(
        cls,
        cell_rect: QRect,
    ) -> tuple[QRect, QRect]:
        total_width = (
            2 * cls.BUTTON_SIZE
            + cls.SPACING
        )

        x = (
            cell_rect.x()
            + max(
                0,
                (cell_rect.width() - total_width) // 2,
            )
        )

        y = (
            cell_rect.y()
            + max(
                0,
                (cell_rect.height() - cls.BUTTON_SIZE) // 2,
            )
        )

        date_rect = QRect(
            x,
            y,
            cls.BUTTON_SIZE,
            cls.BUTTON_SIZE,
        )

        open_rect = QRect(
            x + cls.BUTTON_SIZE + cls.SPACING,
            y,
            cls.BUTTON_SIZE,
            cls.BUTTON_SIZE,
        )

        return date_rect, open_rect

    @classmethod
    def _icon_rect(
        cls,
        button_rect: QRect,
    ) -> QRect:
        x = (
            button_rect.x()
            + (
                button_rect.width()
                - cls.ICON_SIZE
            ) // 2
        )
        y = (
            button_rect.y()
            + (
                button_rect.height()
                - cls.ICON_SIZE
            ) // 2
        )

        return QRect(
            x,
            y,
            cls.ICON_SIZE,
            cls.ICON_SIZE,
        )

    @classmethod
    def _paint_calendar(
        cls,
        painter: QPainter,
        button_rect: QRect,
        *,
        missing: bool,
    ) -> None:
        rect = cls._icon_rect(
            button_rect
        )

        color = (
            QColor(205, 45, 45)
            if missing
            else QColor(145, 145, 145)
        )

        painter.save()
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )

        body = rect.adjusted(
            2,
            4,
            -2,
            -2,
        )

        painter.drawRoundedRect(
            body,
            2,
            2,
        )

        painter.drawLine(
            body.left(),
            body.top() + 4,
            body.right(),
            body.top() + 4,
        )

        painter.drawLine(
            body.left() + 4,
            rect.top() + 1,
            body.left() + 4,
            body.top() + 3,
        )

        painter.drawLine(
            body.right() - 4,
            rect.top() + 1,
            body.right() - 4,
            body.top() + 3,
        )

        # Red exclamation mark makes missing dates obvious.
        if missing:
            center_x = body.center().x()

            painter.drawLine(
                center_x,
                body.top() + 7,
                center_x,
                body.bottom() - 4,
            )
            painter.drawPoint(
                center_x,
                body.bottom() - 2,
            )

        painter.restore()

    @classmethod
    def _paint_open(
        cls,
        painter: QPainter,
        button_rect: QRect,
    ) -> None:
        rect = cls._icon_rect(
            button_rect
        )

        painter.save()
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        color = QColor(90, 90, 90)

        pen = QPen(color)
        pen.setWidth(2)

        painter.setPen(pen)
        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )

        # Small image/frame symbol.
        frame = rect.adjusted(
            2,
            3,
            -2,
            -3,
        )

        painter.drawRect(frame)

        # Mountain/image motif.
        painter.drawLine(
            frame.left() + 2,
            frame.bottom() - 2,
            frame.left() + 7,
            frame.top() + 7,
        )
        painter.drawLine(
            frame.left() + 7,
            frame.top() + 7,
            frame.left() + 10,
            frame.bottom() - 5,
        )
        painter.drawLine(
            frame.left() + 10,
            frame.bottom() - 5,
            frame.right() - 2,
            frame.bottom() - 2,
        )

        painter.drawEllipse(
            frame.right() - 5,
            frame.top() + 2,
            2,
            2,
        )

        painter.restore()
