from pathlib import Path

from PySide6.QtWidgets import QApplication

from photoalbum.album import PageInstance
from photoalbum.gui.template_settings import (
    create_template_settings_editor,
)
from photoalbum.templates.msb.geographic_word_cloud.settings import (
    GeographicWordCloudSettingsWidget,
)
from photoalbum.templates.msb.year_photo_scatter.settings import (
    YearPhotoScatterSettingsWidget,
)
from photoalbum.i18n import Translator
from photoalbum.models import Photo

from photoalbum.template_engine import (
    register_discovered_template_extensions,
)

def ensure_app():
    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    register_discovered_template_extensions()

    return application


def make_photo():
    return Photo(
        path=Path("test.jpg"),
        filename="test.jpg",
    )


def test_scatter_has_its_own_settings_editor():
    ensure_app()

    editor = create_template_settings_editor(
        "year-photo-scatter",
        PageInstance(
            template_id="year-photo-scatter"
        ),
        [make_photo()],
        translator=Translator("fr"),
    )

    assert isinstance(
        editor,
        YearPhotoScatterSettingsWidget,
    )


def test_geographic_cloud_has_its_own_settings_editor():
    ensure_app()

    editor = create_template_settings_editor(
        "geographic-word-cloud",
        PageInstance(
            template_id="geographic-word-cloud"
        ),
        [make_photo()],
        translator=Translator("fr"),
    )

    assert isinstance(
        editor,
        GeographicWordCloudSettingsWidget,
    )


def test_blank_has_its_own_settings_editor():
    ensure_app()

    editor = create_template_settings_editor(
        "blank",
        PageInstance(
            template_id="blank"
        ),
        [make_photo()],
        translator=Translator("fr"),
    )

    assert editor is not None
    assert type(editor).__name__ == (
        "BlankSettingsWidget"
    )
    assert getattr(
        editor,
        "compact_dialog",
        False,
    ) is True


def test_editor_preserves_instance_identity():
    ensure_app()

    instance = PageInstance(
        template_id="geographic-word-cloud"
    )

    editor = create_template_settings_editor(
        instance.template_id,
        instance,
        [],
        translator=Translator("fr"),
    )

    assert editor is not None

    assert (
        editor.instance().instance_id
        == instance.instance_id
    )
