from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget,
)

from photoalbum.i18n import Translator
from photoalbum.rendering.fonts import (
    available_photo_album_fonts, resolve_font_family,
)
from .theme import DEFAULT_MONTH_COLORS, MsbTheme


class MsbThemeDialog(QDialog):
    def __init__(self, theme: MsbTheme, *, translator=None, parent=None):
        super().__init__(parent)
        self._translator = translator or Translator("en")
        self._month_colors = dict(theme.month_colors)
        self._default_font_family = theme.default_font_family
        self._color_buttons = {}
        self.setWindowTitle(self._translator.tr("msb_theme.title"))
        self.setMinimumWidth(720)
        self.resize(780, 500)
        self._create_content()

    def _section_title(self, text):
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        return section

    def _create_content(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        explanation = QLabel(self._translator.tr("msb_theme.explanation"))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        layout.addWidget(self._section_title(self._translator.tr("msb_theme.palette_section")))

        palette = QGridLayout()
        palette.setHorizontalSpacing(16)
        palette.setVerticalSpacing(10)
        for month in range(1, 13):
            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(4)
            cell_layout.addWidget(QLabel(self._translator.month_name(month)))
            button = QPushButton()
            button.setMinimumWidth(120)
            button.clicked.connect(lambda checked=False, m=month: self._choose_month_color(m))
            self._color_buttons[month] = button
            cell_layout.addWidget(button)
            palette.addWidget(cell, (month - 1) // 4, (month - 1) % 4)
            self._update_color_button(month)
        layout.addLayout(palette)

        layout.addSpacing(6)
        layout.addWidget(self._section_title(self._translator.tr("msb_theme.typography_section")))
        form = QFormLayout()
        self._font_combo = QComboBox()
        for family in available_photo_album_fonts():
            self._font_combo.addItem(family, family)
        resolved = resolve_font_family(self._default_font_family)
        index = self._font_combo.findData(resolved)
        if index >= 0:
            self._font_combo.setCurrentIndex(index)
        form.addRow(self._translator.tr("msb_theme.default_font"), self._font_combo)
        layout.addLayout(form)

        footer = QHBoxLayout()
        restore_all = QPushButton(self._translator.tr("msb_theme.restore_all"))
        restore_all.clicked.connect(self._restore_all)
        footer.addWidget(restore_all)
        footer.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        layout.addLayout(footer)

    def _choose_month_color(self, month):
        color = QColorDialog.getColor(QColor(*self._month_colors[month]), self)
        if not color.isValid():
            return
        self._month_colors[month] = (color.red(), color.green(), color.blue())
        self._update_color_button(month)

    def _restore_all(self):
        self._month_colors = dict(DEFAULT_MONTH_COLORS)
        for month in range(1, 13):
            self._update_color_button(month)
        default = MsbTheme()
        self._default_font_family = default.default_font_family
        resolved = resolve_font_family(self._default_font_family)
        index = self._font_combo.findData(resolved)
        if index >= 0:
            self._font_combo.setCurrentIndex(index)

    def _update_color_button(self, month):
        text = "#{:02X}{:02X}{:02X}".format(*self._month_colors[month])
        button = self._color_buttons[month]
        button.setText(text)
        button.setToolTip(text)
        button.setStyleSheet("QPushButton { background-color: " + text + "; min-height: 28px; }")

    def theme(self):
        family = self._font_combo.currentData() or self._default_font_family
        return MsbTheme(month_colors=dict(self._month_colors), default_font_family=str(family))
