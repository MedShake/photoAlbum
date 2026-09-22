from pathlib import Path
from types import SimpleNamespace

from photoalbum.i18n.translator import Translator
from photoalbum.templates.simplex.full_photo_cover.widget_renderer import (
    EXTERNAL_PATH_KEY,
    PHOTO_PATH_KEY,
    SOURCE_EXTERNAL,
    SOURCE_PROJECT,
    SOURCE_TYPE_KEY,
    selected_image_path,
)


class _Instance:
    def __init__(self, settings):
        self.settings = settings


def test_simplex_project_source_resolves_selected_photo():
    first = SimpleNamespace(path=Path("/photos/first.jpg"))
    second = SimpleNamespace(path=Path("/photos/second.jpg"))

    instance = _Instance(
        {
            SOURCE_TYPE_KEY: SOURCE_PROJECT,
            PHOTO_PATH_KEY: str(second.path),
        }
    )

    assert selected_image_path(
        instance,
        [first, second],
    ) == second.path


def test_simplex_external_source_uses_external_path():
    external = Path("/covers/cover.jpg")

    instance = _Instance(
        {
            SOURCE_TYPE_KEY: SOURCE_EXTERNAL,
            EXTERNAL_PATH_KEY: str(external),
        }
    )

    # Project photos must not affect an explicitly external source.
    project_photo = SimpleNamespace(
        path=Path("/photos/project.jpg")
    )

    assert selected_image_path(
        instance,
        [project_photo],
    ) == external


def test_simplex_external_source_without_path_is_empty():
    instance = _Instance(
        {
            SOURCE_TYPE_KEY: SOURCE_EXTERNAL,
            EXTERNAL_PATH_KEY: "",
        }
    )

    assert selected_image_path(instance, []) is None


def test_simplex_legacy_settings_default_to_project_source():
    photo = SimpleNamespace(path=Path("/photos/legacy.jpg"))

    instance = _Instance(
        {
            PHOTO_PATH_KEY: str(photo.path),
        }
    )

    assert selected_image_path(
        instance,
        [photo],
    ) == photo.path


def test_simplex_translations_are_present_in_english_and_french():
    expected = {
        "en": {
            "template.simplex-full-photo-cover":
                "Full-page photo cover",
            "simplex.full-photo-cover.source":
                "Image source",
            "simplex.full-photo-cover.source-project":
                "Project photo",
            "simplex.full-photo-cover.source-external":
                "External file",
            "simplex.full-photo-cover.file":
                "File",
            "simplex.full-photo-cover.browse":
                "Browse…",
            "simplex.full-photo-cover.title-group":
                "Title",
            "simplex.full-photo-cover.title-visible":
                "Show title",
            "simplex.full-photo-cover.title-mode-automatic":
                "Automatic",
            "simplex.full-photo-cover.title-mode-custom":
                "Custom",
            "simplex.full-photo-cover.title-position-center":
                "Centered",
        },
        "fr": {
            "template.simplex-full-photo-cover":
                "Couverture pleine page",
            "simplex.full-photo-cover.source":
                "Source de l’image",
            "simplex.full-photo-cover.source-project":
                "Photo du projet",
            "simplex.full-photo-cover.source-external":
                "Fichier externe",
            "simplex.full-photo-cover.file":
                "Fichier",
            "simplex.full-photo-cover.browse":
                "Parcourir…",
            "simplex.full-photo-cover.title-group":
                "Titre",
            "simplex.full-photo-cover.title-visible":
                "Afficher le titre",
            "simplex.full-photo-cover.title-mode-automatic":
                "Automatique",
            "simplex.full-photo-cover.title-mode-custom":
                "Personnalisé",
            "simplex.full-photo-cover.title-position-center":
                "Centrée",
        },
    }

    for language, translations in expected.items():
        translator = Translator(language)

        for key, value in translations.items():
            assert translator.tr(key) == value
