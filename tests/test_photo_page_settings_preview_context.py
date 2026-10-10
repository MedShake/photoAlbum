from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from photoalbum.album import PageInstance
from photoalbum.album.pagination import PageSide, PlannedPage
from photoalbum.album.planning import PlanItemKind
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.templates.msb.photo_page import settings as settings_module


def make_photo(name):
    return Photo(path=Path(f"/{name}.jpg"), filename=f"{name}.jpg")


def page(number, photos):
    return PlannedPage(
        number, PageSide.RIGHT, PlanItemKind.PHOTO_GROUP, "photo-page-4",
        photos=tuple(photos), photo_capacity=4,
    )


def test_actual_preview_context_wins_and_rerenders_for_successive_pages(monkeypatch):
    QApplication.instance() or QApplication([])
    captured = []

    class Composer:
        def compose(self, candidate, *args, **kwargs):
            captured.append(tuple(photo.identity for photo in candidate.photos))
            return object()

    monkeypatch.setattr(settings_module, "PageComposer", Composer)
    monkeypatch.setattr(
        settings_module.PhotoPageSettingsWidget,
        "render_composition_preview",
        lambda self, *args, **kwargs: QPixmap(1, 1),
    )

    global_photos = tuple(make_photo(name) for name in "ABCDEFGH")
    widget = settings_module.PhotoPageSettingsWidget(
        PageInstance("photo-page-4"), global_photos,
        translator=Translator("en"),
    )
    try:
        assert captured[-1] == tuple(photo.identity for photo in global_photos[:4])

        later = page(2, global_photos[4:6])
        widget.set_album_context(later, [later])
        assert captured[-1] == tuple(photo.identity for photo in global_photos[4:6])

        last = page(3, global_photos[6:8])
        widget.set_album_context(last, [last])
        assert captured[-1] == tuple(photo.identity for photo in global_photos[6:8])

        widget._show_caption.setChecked(not widget._show_caption.isChecked())
        assert captured[-1] == tuple(photo.identity for photo in global_photos[6:8])
    finally:
        widget.close()


def test_preview_capacity_and_generic_fallback(monkeypatch):
    QApplication.instance() or QApplication([])
    captured = []

    class Composer:
        def compose(self, candidate, *args, **kwargs):
            captured.append(tuple(photo.filename for photo in candidate.photos))
            return object()

    monkeypatch.setattr(settings_module, "PageComposer", Composer)
    monkeypatch.setattr(
        settings_module.PhotoPageSettingsWidget,
        "render_composition_preview",
        lambda self, *args, **kwargs: QPixmap(1, 1),
    )
    photos = tuple(make_photo(name) for name in "ABCDE")

    for capacity in (1, 2, 3, 4):
        widget = settings_module.PhotoPageSettingsWidget(
            PageInstance(f"photo-page-{capacity}"), photos,
            translator=Translator("en"),
        )
        try:
            assert captured[-1] == tuple(photo.filename for photo in photos[:capacity])
            occurrence = page(5, photos[1:])
            widget.set_album_context(occurrence, [occurrence])
            assert captured[-1] == tuple(
                photo.filename for photo in photos[1:1 + capacity]
            )
        finally:
            widget.close()


def test_three_photo_layout_group_is_above_captions(monkeypatch):
    from PySide6.QtWidgets import QGroupBox
    from photoalbum.templates.msb.photo_page.settings import PhotoPageSettingsWidget
    monkeypatch.setattr(
        PhotoPageSettingsWidget, "_render_preview", lambda self: None,
    )
    editor = PhotoPageSettingsWidget(
        PageInstance("photo-page-3"), [], translator=Translator("fr"),
    )
    try:
        group_titles = [group.title() for group in editor.findChildren(QGroupBox)]
        assert group_titles.index(editor._translator.tr("page_settings.photo_3_layout_group")) < group_titles.index(editor._translator.tr("page_settings.caption_group"))
    finally:
        editor.close()
