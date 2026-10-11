"""Compact, native-Qt accordion widgets for configuration forms.

The body is really hidden when closed, so its minimum height cannot force
all tabs (and ultimately the main window) to be taller than the display.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)


class AccordionSection(QWidget):
    """A clickable heading and a real QWidget body, without animations or CSS."""

    toggled = Signal(bool)

    def __init__(
        self, title: str, content: QWidget, *, expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._heading = QToolButton(self)
        self._heading.setCheckable(True)
        self._heading.setText(title)
        self._heading.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._heading.setArrowType(Qt.ArrowType.RightArrow)
        self._heading.setAutoRaise(True)
        self._heading.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Let Qt paint its native checked/pressed/focus state.  The V8 custom
        # stylesheet introduced an unwanted white focus rectangle on Windows.
        # Make the native hover/selection surface cover the *whole* row instead
        # of just the left half of the heading.
        self._heading.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._heading.setAccessibleName(title)
        self._heading.toggled.connect(self._on_toggled)

        # The folded summary is a non-interactive overlay on the right of the
        # button. Mouse/keyboard events still reach the full-width heading.
        self._summary = QLabel(self._heading)
        self._summary.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._summary.setVisible(False)
        heading_layout = QHBoxLayout(self._heading)
        heading_layout.setContentsMargins(0, 0, 8, 0)
        heading_layout.setSpacing(0)
        # Reserve the title, then give the summary the remaining space even
        # though its size policy ignores the potentially very long text.
        heading_layout.addSpacing(self._heading.sizeHint().width() + 8)
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
