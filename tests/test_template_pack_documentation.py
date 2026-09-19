import json

import pytest

from photoalbum.template_engine.discovery import (
    discover_template_packs,
    load_template_pack,
)


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

    for pack_id in ("msb", "simplex"):
        pack = packs[pack_id]

        assert pack.documentation_path("en") is not None
        assert pack.documentation_path("fr") is not None

        assert pack.documentation_path("en").name == "help.en.html"
        assert pack.documentation_path("fr").name == "help.fr.html"


def test_documentation_language_selection():
    packs = {
        pack.pack_id: pack
        for pack in discover_template_packs()
    }

    msb = packs["msb"]

    assert msb.documentation_path("fr").name == "help.fr.html"
    assert msb.documentation_path("fr_FR").name == "help.fr.html"
    assert msb.documentation_path("fr-FR").name == "help.fr.html"
    assert msb.documentation_path("en").name == "help.en.html"


def test_unknown_language_falls_back_to_english():
    packs = {
        pack.pack_id: pack
        for pack in discover_template_packs()
    }

    msb = packs["msb"]

    assert msb.documentation_path("de").name == "help.en.html"


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


def test_legacy_string_documentation_is_supported(tmp_path):
    pack = tmp_path / "example"
    pack.mkdir()

    readme = pack / "README.md"
    readme.write_text("# Example", encoding="utf-8")

    manifest = pack / "manifest.json"
    manifest.write_text(
        json.dumps(_manifest("README.md")),
        encoding="utf-8",
    )

    loaded = load_template_pack(manifest)

    assert loaded.documentation_path("en") == readme.resolve()
    assert loaded.documentation_path("fr") == readme.resolve()


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

    for pack_id in ("msb", "simplex"):
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

    for pack_id in ("msb", "simplex"):
        pack = packs[pack_id]

        for path in pack.documentation_paths.values():
            text = path.read_text(encoding="utf-8")

            for term in forbidden:
                assert term not in text
