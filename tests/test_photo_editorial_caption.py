from datetime import datetime
from pathlib import Path

from photoalbum.album.composition import (
    build_photo_caption,
)
from photoalbum.album.settings import (
    PhotoPageSettings,
)
from photoalbum.database import (
    PhotoRepository,
    ProjectDatabase,
)
from photoalbum.models import Photo


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
