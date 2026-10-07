from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QMouseEvent,
    QPainter,
)
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
)

from photoalbum.gui.icon_resources import resource_icon
from photoalbum.i18n import Translator
from photoalbum.models import Photo, PhotoUsage



def _neutral_item_option(option: QStyleOptionViewItem) -> QStyleOptionViewItem:
    """Return an item option without row selection/hover/focus visuals."""
    neutral = QStyleOptionViewItem(option)
    neutral.state &= ~(
        QStyle.StateFlag.State_Selected
        | QStyle.StateFlag.State_MouseOver
        | QStyle.StateFlag.State_HasFocus
    )
    return neutral


class PhotoCellDelegate(QStyledItemDelegate):
    """Default Photos-table delegate with neutral interactive row states."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        super().paint(painter, _neutral_item_option(option), index)


class _PhotoIconPainter:
    """Paint cached outline SVG icons used by the Photos table."""

    ICON_SIZE = 18

    @classmethod
    def icon_rect(cls, button_rect: QRect) -> QRect:
        x = button_rect.x() + (button_rect.width() - cls.ICON_SIZE) // 2
        y = button_rect.y() + (button_rect.height() - cls.ICON_SIZE) // 2
        return QRect(x, y, cls.ICON_SIZE, cls.ICON_SIZE)

    @classmethod
    def paint_icon(
        cls,
        painter: QPainter,
        button_rect: QRect,
        filename: str,
    ) -> None:
        resource_icon(filename).paint(painter, cls.icon_rect(button_rect))


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
            super().paint(painter, _neutral_item_option(option), index)
            return

        base_option = _neutral_item_option(option)
        base_option.text = ""
        QApplication.style().drawControl(
            QStyle.ControlElement.CE_ItemViewItem,
            base_option,
            painter,
        )

        button_rect = self.open_button_rect(option.rect)
        _PhotoIconPainter.paint_icon(painter, button_rect, "photo-open.svg")

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

        painter.save()
        painter.setPen(option.palette.color(option.palette.ColorRole.Text))
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
        base_option = _neutral_item_option(option)
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

        usage_icon = {
            PhotoUsage.BODY: "photo-usage-body.svg",
            PhotoUsage.TEMPLATE_ONLY: "photo-usage-template-only.svg",
            PhotoUsage.OFF: "photo-usage-off.svg",
        }[photo.usage]
        _PhotoIconPainter.paint_icon(painter, usage_rect, usage_icon)

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
    def _paint_calendar(
        cls,
        painter: QPainter,
        button_rect: QRect,
        *,
        missing: bool,
    ) -> None:
        filename = "photo-date-missing.svg" if missing else "photo-date.svg"
        _PhotoIconPainter.paint_icon(painter, button_rect, filename)

    @classmethod
    def _paint_gps(
        cls,
        painter: QPainter,
        button_rect: QRect,
        *,
        missing: bool,
    ) -> None:
        filename = (
            "photo-location-missing.svg" if missing else "photo-location.svg"
        )
        _PhotoIconPainter.paint_icon(painter, button_rect, filename)

