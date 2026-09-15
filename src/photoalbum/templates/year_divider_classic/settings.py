from __future__ import annotations

from dataclasses import replace

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from photoalbum.album import PageInstance
from photoalbum.gui.template_settings.base import (
    PageTemplateSettingsWidget,
)


class YearDividerClassicSettingsWidget(
    PageTemplateSettingsWidget
):

    DEFAULT_TITLE_COLOR = "#d0d0d0"

    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator,
        render_service=None,
        page_format=None,
        parent=None,
    ) -> None:
        super().__init__(
            instance,
            photos,
            translator=translator,
            render_service=render_service,
            page_format=page_format,
            parent=parent,
        )

        settings = instance.settings.get(
            "year_divider",
            {},
        )

        if not isinstance(settings, dict):
            settings = {}

        self._title_color = str(
            settings.get(
                "title_color",
                self.DEFAULT_TITLE_COLOR,
            )
        )

        if not QColor(
            self._title_color
        ).isValid():
            self._title_color = (
                self.DEFAULT_TITLE_COLOR
            )

        self._create_content()

    def _create_content(self) -> None:
        layout = QVBoxLayout(self)

        label = QLabel(
            self._translator.tr(
                "page_settings.title_color"
            )
        )
        layout.addWidget(label)

        self._title_color_button = QPushButton()

        self._title_color_button.clicked.connect(
            self._choose_title_color
        )

        layout.addWidget(
            self._title_color_button
        )
        layout.addStretch()

        self._update_title_color_button()

    def _update_title_color_button(
        self,
    ) -> None:
        self._title_color_button.setText(
            self._translator.tr(
                "page_settings.title_color_value",
                color=self._title_color,
            )
        )

    def _choose_title_color(
        self,
    ) -> None:
        color = QColorDialog.getColor(
            QColor(
                self._title_color
            ),
            self,
            self._translator.tr(
                "page_settings.choose_title_color"
            ),
        )

        if not color.isValid():
            return

        self._title_color = color.name()

        settings = dict(
            self._instance.settings
        )

        settings["year_divider"] = {
            "title_color": self._title_color,
        }

        self._instance = replace(
            self._instance,
            settings=settings,
        )

        self._update_title_color_button()
        self.instance_changed.emit()
