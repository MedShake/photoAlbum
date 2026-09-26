import json
from pathlib import Path
from dataclasses import replace

import pytest

from photoalbum.i18n import Translator
from photoalbum.template_engine import (
    discover_template_packs,
    discover_templates,
    load_template_pack,
    replace_active_template_packs,
    translator_for_template,
)


def builtin_pack(pack_id):
    return next(
        pack for pack in discover_template_packs()
        if pack.pack_id == pack_id
    )


def test_builtin_pack_catalogs_are_localized_and_isolated():
    msb = builtin_pack("msb")
    simplex = builtin_pack("simplex")

    assert msb.translator(Translator("en")).tr("msb_theme.title") == "MSB theme"
    assert msb.translator(Translator("fr")).tr("msb_theme.title") == "Thème MSB"
    assert simplex.translator(Translator("en")).tr(
        "simplex.full-photo-cover.source"
    ) == "Image source"
    assert simplex.translator(Translator("fr")).tr(
        "simplex.full-photo-cover.source"
    ) == "Source de l’image"
    assert msb.translator(Translator("en")).tr(
        "simplex.full-photo-cover.source"
    ) == "simplex.full-photo-cover.source"
    assert simplex.translator(Translator("en")).tr(
        "msb_theme.title"
    ) == "msb_theme.title"


def test_pack_translation_fallback_contract_and_generic_discovery(tmp_path):
    pack = tmp_path / "independent"
    (pack / "i18n").mkdir(parents=True)
    (pack / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "id": "independent",
        "name": "Independent",
        "version": "1.0",
        "templates": [{
            "id": "independent-page",
            "name": "Independent page",
            "module": "page",
            "kinds": ["special_page"],
        }],
    }), encoding="utf-8")
    (pack / "i18n" / "en.json").write_text(json.dumps({
        "pack.english-only": "English fallback",
        "pack.localized": "English",
    }), encoding="utf-8")
    (pack / "i18n" / "fr.json").write_text(json.dumps({
        "pack.localized": "Français",
    }), encoding="utf-8")

    discovered = load_template_pack(pack / "manifest.json")
    french = discovered.translator(Translator("fr"))
    unavailable = discovered.translator(Translator("de"))

    assert french.tr("pack.localized") == "Français"
    assert french.tr("pack.english-only") == "English fallback"
    assert french.tr("plan.summary") == "Résumé"
    assert french.tr("unknown.key") == "unknown.key"
    assert unavailable.tr("pack.localized") == "English"
    assert unavailable.tr("plan.summary") == "Summary"

    active_packs = discover_template_packs()
    replace_active_template_packs(active_packs)
    assert translator_for_template(
        "year-photo-scatter", Translator("fr")
    ).tr("msb_theme.title") == "Thème MSB"

    local_discovery = discover_templates(tmp_path)
    assert local_discovery.registry.get("independent-page") is not None
    assert translator_for_template(
        "year-photo-scatter", Translator("fr")
    ).tr("msb_theme.title") == "Thème MSB"
    assert translator_for_template(
        "independent-page", Translator("fr")
    ).tr("pack.localized") == "pack.localized"


def test_active_pack_replacement_removes_obsolete_catalogs(tmp_path):
    pack = tmp_path / "replacement"
    (pack / "i18n").mkdir(parents=True)
    (pack / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "id": "replacement",
        "name": "Replacement",
        "version": "1.0",
        "templates": [{
            "id": "replacement-page",
            "name": "Replacement page",
            "module": "page",
            "kinds": ["special_page"],
        }],
    }), encoding="utf-8")
    (pack / "i18n" / "en.json").write_text(json.dumps({
        "replacement.label": "Replacement label",
    }), encoding="utf-8")

    replace_active_template_packs(discover_template_packs())
    assert translator_for_template(
        "year-photo-scatter", Translator("fr")
    ).tr("msb_theme.title") == "Thème MSB"

    replacement = discover_template_packs(tmp_path)
    replace_active_template_packs(replacement)
    assert translator_for_template(
        "replacement-page", Translator("fr")
    ).tr("replacement.label") == "Replacement label"
    assert translator_for_template(
        "year-photo-scatter", Translator("fr")
    ).tr("msb_theme.title") == "msb_theme.title"

    replace_active_template_packs(())
    assert translator_for_template(
        "replacement-page", Translator("en")
    ).tr("replacement.label") == "replacement.label"
    replace_active_template_packs(discover_template_packs())


def test_active_pack_replacement_rejects_template_collision_atomically():
    msb = builtin_pack("msb")
    simplex = builtin_pack("simplex")
    replace_active_template_packs((msb, simplex))
    colliding_template = replace(
        simplex.templates[0],
        template_id=msb.templates[0].template_id,
    )
    colliding_simplex = replace(
        simplex,
        templates=(colliding_template,),
    )

    with pytest.raises(
        ValueError,
        match="Duplicate active template ID: year-photo-scatter",
    ):
        replace_active_template_packs((msb, colliding_simplex))

    assert translator_for_template(
        "year-photo-scatter", Translator("fr")
    ).tr("msb_theme.title") == "Thème MSB"
    assert translator_for_template(
        "simplex-full-photo-cover", Translator("fr")
    ).tr("simplex.full-photo-cover.source") == "Source de l’image"


def test_active_pack_replacement_rejects_duplicate_pack_id_atomically():
    active_packs = discover_template_packs()
    replace_active_template_packs(active_packs)
    duplicate = replace(active_packs[0], templates=())

    with pytest.raises(
        ValueError,
        match=f"Duplicate active template pack ID: {active_packs[0].pack_id}",
    ):
        replace_active_template_packs((active_packs[0], duplicate))

    assert translator_for_template(
        "year-photo-scatter", Translator("fr")
    ).tr("msb_theme.title") == "Thème MSB"
