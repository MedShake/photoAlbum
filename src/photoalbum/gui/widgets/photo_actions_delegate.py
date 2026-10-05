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

from photoalbum.i18n import Translator
from photoalbum.models import Photo, PhotoUsage


class _PhotoIconPainter:
    """Shared painter for the photo-shaped action icons."""

    ICON_SIZE = 20

    @classmethod
    def icon_rect(cls, button_rect: QRect) -> QRect:
        x = button_rect.x() + (button_rect.width() - cls.ICON_SIZE) // 2
        y = button_rect.y() + (button_rect.height() - cls.ICON_SIZE) // 2
        return QRect(x, y, cls.ICON_SIZE, cls.ICON_SIZE)

    @classmethod
    def paint_photo_icon(
        cls,
        painter: QPainter,
        button_rect: QRect,
        *,
        color: QColor | None = None,
        badge_color: QColor | None = None,
        badge_symbol: str | None = None,
    ) -> None:
        rect = cls.icon_rect(button_rect)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        base_color = color or QColor(90, 90, 90)
        pen = QPen(base_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Same image/frame symbol for both "open" and usage actions.
        frame = rect.adjusted(2, 3, -2, -3)
        painter.drawRect(frame)

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

        if badge_color is not None and badge_symbol:
            badge_size = 10
            badge = QRect(
                rect.right() - badge_size + 2,
                rect.bottom() - badge_size + 2,
                badge_size,
                badge_size,
            )
            painter.setPen(QPen(badge_color, 1))
            painter.setBrush(badge_color)
            painter.drawEllipse(badge)

            font = painter.font()
            font.setPixelSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor("white"))
            painter.drawText(
                badge,
                Qt.AlignmentFlag.AlignCenter,
                badge_symbol,
            )

        painter.restore()


class PhotoFilenameDelegate(QStyledItemDelegate):
    """Render the filename cell with a clickable OS-open photo icon."""

    open_photo_requested = Signal(object)

    BUTTON_SIZE = 30
    LEFT_PADDING = 2
    TEXT_GAP = 3

    def __init__(
        self,
        parent=None,
        *,
        translator: Translator | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator or Translator("fr")

    @classmethod
    def open_button_rect(cls, cell_rect: QRect) -> QRect:
        y = cell_rect.y() + max(0, (cell_rect.height() - cls.BUTTON_SIZE) // 2)
        return QRect(
            cell_rect.x() + cls.LEFT_PADDING,
            y,
            cls.BUTTON_SIZE,
            cls.BUTTON_SIZE,
        )

    @classmethod
    def is_over_open_icon(cls, cell_rect: QRect, position) -> bool:
        return cls.open_button_rect(cell_rect).contains(position)

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        return QSize(
            size.width() + self.BUTTON_SIZE + self.TEXT_GAP,
            max(size.height(), self.BUTTON_SIZE),
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        photo = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(photo, Photo):
            super().paint(painter, option, index)
            return

        base_option = QStyleOptionViewItem(option)
        base_option.text = ""
        QApplication.style().drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            base_option,
            painter,
        )

        button_rect = self.open_button_rect(option.rect)
        _PhotoIconPainter.paint_photo_icon(painter, button_rect)

        text_rect = option.rect.adjusted(
            self.LEFT_PADDING + self.BUTTON_SIZE + self.TEXT_GAP,
            0,
            -4,
            0,
        )
        text = option.fontMetrics.elidedText(
            photo.filename,
            Qt.TextElideMode.ElideRight,
            max(0, text_rect.width()),
        )

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette_role = (
            option.palette.ColorRole.HighlightedText
            if selected
            else option.palette.ColorRole.Text
        )

        painter.save()
        painter.setPen(option.palette.color(palette_role))
        painter.setFont(option.font)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text,
        )
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            photo = index.data(Qt.ItemDataRole.UserRole)
            if isinstance(photo, Photo):
                position = event.position().toPoint()
                if self.open_button_rect(option.rect).contains(position):
                    self.open_photo_requested.emit(photo)
                    return True

        return super().editorEvent(event, model, option, index)

    def helpEvent(self, event, view, option, index) -> bool:
        photo = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(photo, Photo):
            return super().helpEvent(event, view, option, index)

        if self.open_button_rect(option.rect).contains(event.pos()):
            QToolTip.showText(
                event.globalPos(),
                self._translator.tr("photos.action.open_image"),
                view,
            )
            return True

        QToolTip.hideText()
        return False


class PhotoActionsDelegate(QStyledItemDelegate):
    """
    Paint and handle the editing actions available for a photo row.

    Opening the photo itself belongs to the filename column; this delegate
    contains only date, GPS and usage actions.
    """

    edit_datetime_requested = Signal(object)
    edit_gps_requested = Signal(object)
    edit_usage_requested = Signal(object)

    ICON_SIZE = 20
    BUTTON_SIZE = 30
    SPACING = 4

    def __init__(
        self,
        parent=None,
        *,
        translator: Translator | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator or Translator("fr")

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        return QSize(
            3 * self.BUTTON_SIZE + 2 * self.SPACING,
            max(size.height(), self.BUTTON_SIZE),
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        base_option = QStyleOptionViewItem(option)
        base_option.text = ""
        QApplication.style().drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            base_option,
            painter,
        )

        photo = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(photo, Photo):
            return

        date_rect, gps_rect, usage_rect = self._action_rects(option.rect)

        self._paint_calendar(
            painter,
            date_rect,
            missing=photo.capture_datetime is None,
        )
        self._paint_gps(
            painter,
            gps_rect,
            missing=not photo.has_gps,
        )

        color, symbol = {
            PhotoUsage.BODY: (QColor("#707070"), "+"),
            PhotoUsage.TEMPLATE_ONLY: (QColor("#B8860B"), "−"),
            PhotoUsage.OFF: (QColor("#C62828"), "×"),
        }[photo.usage]
        _PhotoIconPainter.paint_photo_icon(
            painter,
            usage_rect,
            badge_color=color,
            badge_symbol=symbol,
        )

    def editorEvent(self, event, model, option, index) -> bool:
        if (
            event.type() != QEvent.Type.MouseButtonRelease
            or not isinstance(event, QMouseEvent)
            or event.button() != Qt.MouseButton.LeftButton
        ):
            return super().editorEvent(event, model, option, index)

        photo = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(photo, Photo):
            return False

        date_rect, gps_rect, usage_rect = self._action_rects(option.rect)
        position = event.position().toPoint()

        if usage_rect.contains(position):
            self.edit_usage_requested.emit(photo)
            return True
        if date_rect.contains(position):
            self.edit_datetime_requested.emit(photo)
            return True
        if gps_rect.contains(position):
            self.edit_gps_requested.emit(photo)
            return True

        return False

    def helpEvent(self, event, view, option, index) -> bool:
        photo = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(photo, Photo):
            return super().helpEvent(event, view, option, index)

        date_rect, gps_rect, usage_rect = self._action_rects(option.rect)
        position = event.pos()

        if usage_rect.contains(position):
            QToolTip.showText(
                event.globalPos(),
                self._translator.tr("photos.usage." + photo.usage.value),
                view,
            )
            return True

        if date_rect.contains(position):
            QToolTip.showText(
                event.globalPos(),
                self._translator.tr("photos.action.set_datetime"),
                view,
            )
            return True

        if gps_rect.contains(position):
            QToolTip.showText(
                event.globalPos(),
                self._translator.tr("photos.action.set_location"),
                view,
            )
            return True

        QToolTip.hideText()
        return False

    @classmethod
    def _action_rects(cls, cell_rect: QRect) -> tuple[QRect, QRect, QRect]:
        total_width = 3 * cls.BUTTON_SIZE + 2 * cls.SPACING
        x = cell_rect.x() + max(0, (cell_rect.width() - total_width) // 2)
        y = cell_rect.y() + max(0, (cell_rect.height() - cls.BUTTON_SIZE) // 2)

        date_rect = QRect(x, y, cls.BUTTON_SIZE, cls.BUTTON_SIZE)
        gps_rect = QRect(
            x + cls.BUTTON_SIZE + cls.SPACING,
            y,
            cls.BUTTON_SIZE,
            cls.BUTTON_SIZE,
        )
        usage_rect = QRect(
            x + 2 * (cls.BUTTON_SIZE + cls.SPACING),
            y,
            cls.BUTTON_SIZE,
            cls.BUTTON_SIZE,
        )
        return date_rect, gps_rect, usage_rect

    @classmethod
    def _icon_rect(cls, button_rect: QRect) -> QRect:
        x = button_rect.x() + (button_rect.width() - cls.ICON_SIZE) // 2
        y = button_rect.y() + (button_rect.height() - cls.ICON_SIZE) // 2
        return QRect(x, y, cls.ICON_SIZE, cls.ICON_SIZE)

    @classmethod
    def _paint_calendar(
        cls,
        painter: QPainter,
        button_rect: QRect,
        *,
        missing: bool,
    ) -> None:
        rect = cls._icon_rect(button_rect)
        color = QColor(205, 45, 45) if missing else QColor(145, 145, 145)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        body = rect.adjusted(2, 4, -2, -2)
        painter.drawRoundedRect(body, 2, 2)
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

        if missing:
            center_x = body.center().x()
            painter.drawLine(
                center_x,
                body.top() + 7,
                center_x,
                body.bottom() - 4,
            )
            painter.drawPoint(center_x, body.bottom() - 2)

        painter.restore()

    @classmethod
    def _paint_gps(
        cls,
        painter: QPainter,
        button_rect: QRect,
        *,
        missing: bool,
    ) -> None:
        rect = cls._icon_rect(button_rect)
        color = QColor(205, 45, 45) if missing else QColor(145, 145, 145)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        center_x = rect.center().x()
        top = rect.top() + 2

        painter.drawEllipse(center_x - 5, top, 10, 10)
        painter.drawEllipse(center_x - 1, top + 4, 2, 2)
        painter.drawLine(
            center_x - 4,
            top + 9,
            center_x,
            rect.bottom() - 1,
        )
        painter.drawLine(
            center_x + 4,
            top + 9,
            center_x,
            rect.bottom() - 1,
        )

        if missing:
            painter.drawLine(
                rect.right() - 3,
                rect.top() + 2,
                rect.right() - 3,
                rect.top() + 8,
            )
            painter.drawPoint(rect.right() - 3, rect.top() + 11)

        painter.restore()
