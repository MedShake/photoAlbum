from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from photoalbum.templates.msb.photo_page.composition import build_photo_caption
from photoalbum.album.settings import (
    PhotoPageSettings,
)
from photoalbum.database import (
    PhotoRepository,
    ProjectDatabase,
)
from photoalbum.models import Photo
from photoalbum.gui.widgets.photo_places_widget import PhotoPlacesWidget


def test_repository_persists_editorial_caption(
    tmp_path: Path,
):
    database = ProjectDatabase(
        tmp_path / "project.sqlite3"
    )
    database.initialize()

    repository = PhotoRepository(database)

    photo = Photo(
        path=tmp_path / "photo.jpg",
        filename="photo.jpg",
        capture_datetime=datetime(
            2025,
            7,
            14,
            12,
            30,
        ),
    )

    repository.save(photo)

    repository.set_caption(
        photo.path,
        "Départ du port",
    )

    loaded = repository.find_by_path(
        photo.path
    )

    assert loaded is not None
    assert loaded.caption == "Départ du port"

    repository.set_caption(
        photo.path,
        "   ",
    )

    loaded = repository.find_by_path(
        photo.path
    )

    assert loaded is not None
    assert loaded.caption is None

    database.close()


def test_editorial_caption_is_part_of_album_caption():
    photo = Photo(
        path=Path("photo.jpg"),
        filename="photo.jpg",
        caption="Départ du port",
    )

    content = build_photo_caption(
        photo,
        PhotoPageSettings(
            template_id="msb.photo",
        ),
    )

    assert content.caption_text == "Départ du port"
    assert content.line_count >= 1

def test_caption_and_datetime_share_one_display_line():
    from photoalbum.templates.msb.photo_page.composition import PhotoCaptionContent

    content = PhotoCaptionContent(
        capture_datetime=datetime(
            2025,
            7,
            14,
            12,
            30,
        ),
        location_text="Saint-Malo",
        caption_text="Départ du port",
    )

    assert content.line_count == 2


def test_caption_without_location_uses_one_display_line():
    from photoalbum.templates.msb.photo_page.composition import PhotoCaptionContent

    content = PhotoCaptionContent(
        capture_datetime=datetime(
            2025,
            7,
            14,
            12,
            30,
        ),
        caption_text="Départ du port",
    )

    assert content.line_count == 1


def test_caption_without_datetime_still_uses_first_line():
    from photoalbum.templates.msb.photo_page.composition import PhotoCaptionContent

    content = PhotoCaptionContent(
        location_text="Saint-Malo",
        caption_text="Départ du port",
    )

    assert content.line_count == 2


def test_imported_caption_is_a_searchable_editor_suggestion():
    app = QApplication.instance() or QApplication([])
    widget = PhotoPlacesWidget()
    photo = Photo(
        path=Path("remote.jpg"),
        filename="remote.jpg",
        capture_datetime=datetime(2025, 7, 14),
        imported_caption="Provider description",
    )
    widget._caption_result = lambda _photo: SimpleNamespace(
        candidates=(), selected=(), caption=None,
    )
    widget.set_photos([photo])
    year = widget._tree.topLevelItem(0)
    year.setExpanded(True)
    month = year.child(0)
    month.setExpanded(True)
    for _ in range(5):
        app.processEvents()

    editor = widget._caption_editors[str(photo.path)]
    assert editor.text() == ""
    assert editor.placeholderText() == "Provider description"
    assert photo.caption is None

    widget._filter_text = "provider"
    assert widget._matches_filter(photo) is True
    widget.close()
