import json
from shutil import copytree, ignore_patterns

import pytest
from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication, QDialog

from photoalbum.gui import main_window, template_pack_help_dialog
from photoalbum.gui.template_pack_help_dialog import TemplatePackHelpDialog
from photoalbum.i18n import Translator
from photoalbum.template_engine.discovery import (
    discover_template_packs,
    load_template_pack,
)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _manifest(documentation=None):
    data = {
        "schema_version": 1,
        "id": "example",
        "name": "Example",
        "version": "1.0",
        "templates": [],
    }

    if documentation is not None:
        data["documentation"] = documentation

    return data


def test_builtin_packs_expose_localized_documentation():
    packs = {
        pack.pack_id: pack
        for pack in discover_template_packs()
    }

    for pack_id in ("msb", "simplex", "complex"):
        pack = packs[pack_id]

        assert pack.documentation_path("en") is not None
        assert pack.documentation_path("fr") is not None

        assert pack.documentation_path("en").name == "help.en.html"
        assert pack.documentation_path("fr").name == "help.fr.html"


@pytest.mark.parametrize("pack_id", ["msb", "simplex", "complex"])
def test_documentation_language_selection(pack_id):
    packs = {
        pack.pack_id: pack
        for pack in discover_template_packs()
    }

    pack = packs[pack_id]

    assert pack.documentation_path("fr").name == "help.fr.html"
    assert pack.documentation_path("fr_FR").name == "help.fr.html"
    assert pack.documentation_path("fr-FR").name == "help.fr.html"
    assert pack.documentation_path("en").name == "help.en.html"


@pytest.mark.parametrize("pack_id", ["msb", "simplex", "complex"])
def test_unknown_language_falls_back_to_english(pack_id):
    packs = {
        pack.pack_id: pack
        for pack in discover_template_packs()
    }

    pack = packs[pack_id]

    assert pack.documentation_path("de").name == "help.en.html"


def test_pack_without_documentation_is_supported(tmp_path):
    pack = tmp_path / "example"
    pack.mkdir()

    manifest = pack / "manifest.json"
    manifest.write_text(
        json.dumps(_manifest()),
        encoding="utf-8",
    )

    loaded = load_template_pack(manifest)

    assert loaded.documentation_paths == {}
    assert loaded.documentation_path("fr") is None



def test_documentation_must_use_language_mapping(tmp_path):
    pack = tmp_path / "example"
    pack.mkdir()

    manifest = pack / "manifest.json"
    manifest.write_text(
        json.dumps(_manifest("README.md")),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="language/path mapping"):
        load_template_pack(manifest)


def test_localized_documentation_is_resolved(tmp_path):
    pack = tmp_path / "example"
    docs = pack / "docs"
    docs.mkdir(parents=True)

    english = docs / "help.en.html"
    french = docs / "help.fr.html"

    english.write_text("# English", encoding="utf-8")
    french.write_text("# Français", encoding="utf-8")

    manifest = pack / "manifest.json"
    manifest.write_text(
        json.dumps(
            _manifest(
                {
                    "en": "docs/help.en.html",
                    "fr": "docs/help.fr.html",
                }
            )
        ),
        encoding="utf-8",
    )

    loaded = load_template_pack(manifest)

    assert loaded.documentation_path("en") == english.resolve()
    assert loaded.documentation_path("fr") == french.resolve()


def test_pack_documentation_cannot_escape_pack(tmp_path):
    pack = tmp_path / "example"
    pack.mkdir()

    outside = tmp_path / "outside.md"
    outside.write_text("# Outside", encoding="utf-8")

    manifest = pack / "manifest.json"
    manifest.write_text(
        json.dumps(
            _manifest({"en": "../outside.md"})
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="must remain inside",
    ):
        load_template_pack(manifest)


def test_builtin_documentation_has_english_and_french():
    packs = {
        pack.pack_id: pack
        for pack in discover_template_packs()
    }

    for pack_id in ("msb", "simplex", "complex"):
        pack = packs[pack_id]

        assert "en" in pack.documentation_paths
        assert "fr" in pack.documentation_paths

        for language in ("en", "fr"):
            path = pack.documentation_paths[language]
            assert path.is_file()
            assert path.read_text(
                encoding="utf-8"
            ).strip()


def test_builtin_help_is_user_facing_not_developer_documentation():
    packs = {
        pack.pack_id: pack
        for pack in discover_template_packs()
    }

    forbidden = (
        "PageTemplateExtension",
        "register()",
        "Rendering contract",
        "Implementation structure",
    )

    for pack_id in ("msb", "simplex", "complex"):
        pack = packs[pack_id]

        for path in pack.documentation_paths.values():
            text = path.read_text(encoding="utf-8")

            for term in forbidden:
                assert term not in text


def _assert_complex_help_is_open(dialog, language, pack):
    row = next(
        index
        for index in range(dialog._pack_list.count())
        if dialog._pack_list.item(index).data(Qt.ItemDataRole.UserRole) == "complex"
    )
    dialog._pack_list.setCurrentRow(row)
    assert dialog._pack_list.currentItem().text() == "Complex"

    text = dialog._browser.toPlainText()
    headings = (
        ("Une photo", "Deux photos", "Trois photos", "Quatre photos", "Cinq photos",
         "Mode automatique — 1 à 5 photos")
        if language == "fr" else
        ("One photo", "Two photos", "Three photos", "Four photos", "Five photos",
         "Automatic mode — 1 to 5 photos")
    )
    for heading in headings:
        assert heading in text

    path = pack.documentation_path(language)
    document = dialog._browser.document()
    assert document.baseUrl() == QUrl(path.parent.as_uri() + "/")
    image = document.resource(
        QTextDocument.ResourceType.ImageResource, QUrl("preview_landscape.png")
    )
    assert image is not None
    assert not image.isNull()


@pytest.mark.parametrize("language", ["fr", "en"])
def test_complex_help_opens_from_main_window_menu(app, monkeypatch, tmp_path, language):
    settings = QSettings(str(tmp_path / "window.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, "QSettings", lambda *args: settings)
    opened = []

    def capture_dialog(dialog):
        opened.append(dialog)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(TemplatePackHelpDialog, "exec", capture_dialog)
    window = main_window.MainWindow(language=language)
    try:
        window._template_help_action.trigger()
        assert len(opened) == 1
        dialog = opened[0]
        pack = next(pack for pack in dialog._packs if pack.pack_id == "complex")
        _assert_complex_help_is_open(dialog, language, pack)
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()


@pytest.mark.parametrize("language", ["fr", "en"])
def test_complex_help_opens_with_only_its_own_pack(app, monkeypatch, tmp_path, language):
    source = next(pack for pack in discover_template_packs() if pack.pack_id == "complex")
    isolated_path = copytree(
        source.path, tmp_path / "complex", ignore=ignore_patterns("__pycache__")
    )
    packs = discover_template_packs(isolated_path.parent)
    assert [pack.pack_id for pack in packs] == ["complex"]
    monkeypatch.setattr(template_pack_help_dialog, "discover_template_packs", lambda: packs)

    dialog = TemplatePackHelpDialog(Translator(language))
    try:
        assert dialog._pack_list.count() == 1
        _assert_complex_help_is_open(dialog, language, packs[0])
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
