from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication, QComboBox, QDialog

from photoalbum.album import AlbumBuilder, PageOrientation
from photoalbum.gui import plan_page_editor
from photoalbum.gui.widgets import AlbumSettingsWidget
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.template_engine import create_template_registry


def test_successive_plan_edits_preview_the_current_page_and_new_capacity(monkeypatch):
    QApplication.instance() or QApplication([])
    registry = create_template_registry()
    host = AlbumSettingsWidget(registry)
    settings = host.settings()
    settings.day_dividers = replace(settings.day_dividers, enabled=False)
    settings.month_dividers = replace(settings.month_dividers, enabled=False)
    settings.year_dividers = replace(settings.year_dividers, enabled=False)
    settings.orientation = PageOrientation.LANDSCAPE
    photos = [
        Photo(
            path=Path(f"/{index}.jpg"),
            filename=f"{index}.jpg",
            capture_datetime=datetime(2025, 3, index + 1),
            width=900,
            height=600,
        )
        for index in range(6)
    ]
    result = AlbumBuilder(registry).build(photos, settings)
    pages = [page for page in result.pagination.pages if page.photos]
    assert all(len(page.photos) == 1 for page in pages)

    selected_template = {"id": "photo-page-4"}

    def accept_selector(dialog):
        combo = next(
            item for item in dialog.findChildren(QComboBox)
            if item.findData(selected_template["id"]) >= 0
        )
        combo.setCurrentIndex(combo.findData(selected_template["id"]))
        return QDialog.DialogCode.Accepted

    previews = []

    class FakePageInstanceDialog:
        THEME_REQUESTED = 2

        def __init__(self, instance, photos, **kwargs):
            self._instance = instance
            self._pack_settings = kwargs["template_pack_settings"]
            previews.append(tuple(
                photo.identity for photo in kwargs["preview_page"].photos
            ))

        def exec(self):
            return QDialog.DialogCode.Accepted

        def instance(self):
            return self._instance

        def template_pack_settings(self):
            return self._pack_settings

    monkeypatch.setattr(QDialog, "exec", accept_selector)
    monkeypatch.setattr(plan_page_editor, "PageInstanceDialog", FakePageInstanceDialog)

    try:
        first_page = pages[2]
        plan_page_editor.choose_page(
            None, registry, settings, result, Translator("en"),
            page=first_page, instance=first_page.page_instance, photo_override=True,
        )
        assert previews[-1] == tuple(photo.identity for photo in photos[2:6])

        selected_template["id"] = "photo-page-2"
        second_page = pages[4]
        plan_page_editor.choose_page(
            None, registry, settings, result, Translator("en"),
            page=second_page, instance=second_page.page_instance, photo_override=True,
        )
        assert previews[-1] == tuple(photo.identity for photo in photos[4:6])
    finally:
        host.close()
