from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from photoalbum.album import (
    A4,
    PageFormat,
    PageInstance,
)
from photoalbum.templates.msb.settings_base import (
    MsbTemplateSettingsWidget,
)


class PhotoPageSettingsWidget(
    MsbTemplateSettingsWidget
):
    """Settings entry point shared by photo-page-1..4."""

    def __init__(
        self,
        instance: PageInstance,
        photos,
        *,
        translator,
        render_service=None,
        page_format: PageFormat = A4,
        template_pack_settings=None,
        parent=None,
    ) -> None:
        super().__init__(
            instance,
            photos,
            translator=translator,
            render_service=render_service,
            page_format=page_format,
            template_pack_settings=template_pack_settings,
            parent=parent,
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(
            self.create_page_settings_title()
        )
        layout.addWidget(
            self.create_no_page_settings_label()
        )

        layout.addSpacing(12)

        layout.addWidget(
            self.create_msb_theme_group()
        )
