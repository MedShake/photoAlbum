from __future__ import annotations


from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from photoalbum.album import A4, PageFormat, PageInstance
from photoalbum.album.planning import PlanItemKind
from photoalbum.templates.msb.settings_base import MsbTemplateSettingsWidget


class MonthDividerClassicSettingsWidget(MsbTemplateSettingsWidget):
    PREVIEW_WIDTH=420
    SAMPLE_CITIES = (
        "Bussy-lès-Daours",
        "Amiens",
        "Rennes",
        "Pléneuf-Val-André",
        "Orvault",
        "Nantes",
        "Saint-Herblain",
    )

    def __init__(self, instance: PageInstance, photos, *, translator, render_service=None,
                 page_format: PageFormat=A4, template_pack_settings=None, parent=None) -> None:
        super().__init__(instance,photos,translator=translator,render_service=render_service,page_format=page_format,template_pack_settings=template_pack_settings,parent=parent)
        root=QHBoxLayout(self); root.setSpacing(28)
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(12)
        ll.addWidget(self.create_page_settings_title()); ll.addWidget(self.create_no_page_settings_label())
        note=QLabel(self._translator.tr("month_divider.sample_cities_note")); note.setWordWrap(True); ll.addWidget(note); ll.addSpacing(12); ll.addWidget(self.create_msb_theme_group())
        self._preview = self.create_preview_label(self.PREVIEW_WIDTH)
        self.add_settings_columns(root, left, self._preview)
        self._render_preview()

    def _render_preview(self):
        self._preview.setPixmap(
            self.render_template_preview(
                width=self._preview.width(), height=self._preview.height(), photos=(),
                kind=PlanItemKind.MONTH_DIVIDER,
                page_attributes={"year": 2025, "month": 6, "cities": self.SAMPLE_CITIES},
            )
        )

    def msb_theme_changed(self): self._render_preview()
