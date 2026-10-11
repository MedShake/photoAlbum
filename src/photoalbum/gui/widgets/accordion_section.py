"""Compact, native-Qt accordion widgets for configuration forms.

The body is really hidden when closed, so its minimum height cannot force
all tabs (and ultimately the main window) to be taller than the display.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)


class _AccordionHeader(QToolButton):
    """Platform-independent painting, native button keyboard/mouse semantics.

    Qt's QToolButton checked/hover rendering can turn into a dark, centered
    button on Windows.  Only its appearance is customized here; toggling,
    focus navigation and accessibility remain those of a regular button.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMinimumHeight(25)
        self._keyboard_focus = False

    def focusInEvent(self, event) -> None:
        self._keyboard_focus = event.reason() in (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        )
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        self._keyboard_focus = False
        super().focusOutEvent(event)
        self.update()

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        if self.isChecked():
            background = QColor("#e9ebed")
            border = QColor("#bfc5ca")
        elif self.underMouse():
            background = QColor("#f0f2f4")
            border = QColor("#d4d8dc")
        else:
            background = QColor("#fafafa")
            border = QColor("#e1e3e5")
        painter.setPen(QPen(border, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 2, 2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#555c62") if self.isEnabled() else QColor("#a9adb0"))
        x, y = 11.0, self.height() / 2.0
        if self.isChecked():
            points = [(x - 4, y - 2), (x + 4, y - 2), (x, y + 2)]
        else:
            points = [(x - 2, y - 4), (x - 2, y + 4), (x + 2, y)]
        painter.drawPolygon(QPolygonF([QPointF(px, py) for px, py in points]))

        summary = getattr(self.parent(), "_summary", None)
        # The summary is a child QLabel and remains readable to screen readers.
        # Its geometry bounds the available title width.
        text_right = summary.x() - 7 if summary is not None and summary.isVisible() else self.width() - 9
        text_rect = self.rect().adjusted(23, 0, -max(8, self.width() - text_right), 0)
        painter.setPen(QColor("#30353a") if self.isEnabled() else QColor("#9ba0a4"))
        text = painter.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, max(0, text_rect.width())
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        if self._keyboard_focus:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#477aa0"), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -3, -3), 2, 2)
        painter.end()


class AccordionSection(QWidget):
    """A clickable heading and a real QWidget body, without animations."""

    toggled = Signal(bool)

    def __init__(
        self, title: str, content: QWidget, *, expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._heading = _AccordionHeader(self)
        self._heading.setCheckable(True)
        self._heading.setText(title)
        self._heading.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._heading.setArrowType(Qt.ArrowType.RightArrow)
        self._heading.setAutoRaise(True)
        self._heading.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Paint the row identically across platforms without QSS or native
        # QToolButton chrome. The whole line is still a real Qt button.
        self._heading.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._heading.setAccessibleName(title)
        self._heading.toggled.connect(self._on_toggled)

        # The folded summary is a non-interactive overlay on the right of the
        # button. Mouse/keyboard events still reach the full-width heading.
        self._summary = QLabel(self._heading)
        self._summary.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._summary.setStyleSheet("color: #626a70; background: transparent; border: none;")
        self._summary.setVisible(False)
        heading_layout = QHBoxLayout(self._heading)
        heading_layout.setContentsMargins(0, 0, 8, 0)
        heading_layout.setSpacing(0)
        # Reserve the title, then give the summary the remaining space even
        # though its size policy ignores the potentially very long text.
        heading_layout.addSpacing(self._heading.fontMetrics().horizontalAdvance(title) + 33)
        heading_layout.addWidget(self._summary, 1)

        self.content = content
        self.content.setParent(self)
        # Existing group boxes already contain the real form. Their redundant
        # title would waste vertical space below the new accordion heading.
        from PySide6.QtWidgets import QGroupBox
        if isinstance(content, QGroupBox):
            content.setTitle("")
            content.setFlat(True)
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._heading)
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        layout.addWidget(content)
        self.set_expanded(expanded)

    @property
    def expanded(self) -> bool:
        return self._heading.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self._heading.setChecked(bool(expanded))
        # setChecked(False) on the already-false default emits no signal.
        self._on_toggled(bool(expanded), emit=False)

    def set_summary(self, summary: str) -> None:
        self._summary.setText(summary)
        self._summary.setToolTip(summary)
        self._summary.setVisible(bool(summary) and not self.expanded)

    def _on_toggled(self, expanded: bool, *, emit: bool = True) -> None:
        self.content.setVisible(expanded)
        self._summary.setVisible(bool(self._summary.text()) and not expanded)
        self._heading.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.updateGeometry()
        if emit:
            self.toggled.emit(expanded)


class AccordionGroup:
    """Manage accordion sections, with optional exclusive expansion.

    Album settings and PDF options use ``exclusive=True`` so opening one
    section closes the previous one on small screens.
    """

    def __init__(self, *, exclusive: bool = False) -> None:
        self.sections: dict[str, AccordionSection] = {}
        self.exclusive = exclusive

    def add(self, key: str, section: AccordionSection) -> AccordionSection:
        if key in self.sections:
            raise ValueError(f"Accordion section already registered: {key}")
        self.sections[key] = section
        if self.exclusive:
            section.toggled.connect(
                lambda expanded, active=section: self._on_toggled(active, expanded)
            )
        return section

    def _on_toggled(self, active: AccordionSection, expanded: bool) -> None:
        if expanded:
            for section in self.sections.values():
                if section is not active and section.expanded:
                    section.set_expanded(False)

    def collapse_all(self) -> None:
        for section in self.sections.values():
            section.set_expanded(False)
