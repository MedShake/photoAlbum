"""Pack-owned names, legacy fallbacks and the labels shown by the GUI."""
from dataclasses import replace
import json

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

from photoalbum.album import AutomaticPhotoPageModeDefinition, PageInstance, TemplateDefinition, TemplateKind
from photoalbum.gui.page_instance_dialog import PageInstanceDialog
from photoalbum.gui.template_labels import automatic_photo_page_mode_display_name, template_display_name
from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.i18n import Translator
from photoalbum.template_engine import discovery, translations
from photoalbum.template_engine.extensions import template_extension_registry


ORDINARY_NAMES = [
    ("msb", "year-photo-scatter", "Year photo scatter", "Pêle-mêle annuel"),
    ("msb", "geographic-word-cloud", "Geographic word cloud", "Nuage géographique"),
    ("msb", "geographic-map", "Geographic map", "Carte géographique"),
    ("msb", "calendar-index", "Annual calendar", "Calendrier annuel"),
    ("msb", "year-divider-classic", "Simple year divider", "Séparateur d’année simple"),
    ("msb", "month-divider-classic", "Month divider with city list", "Séparateur de mois avec liste des villes"),
    ("msb", "month-divider-simple", "Simple month divider", "Séparateur de mois simple"),
    ("msb", "day-divider-simple", "Simple day divider", "Séparateur de jour simple"),
    ("msb", "dedication", "Dedication", "Dédicace"),
    ("msb", "blank", "Blank page", "Page blanche"),
    ("msb", "photo-page-1", "One photo", "Une photo"),
    ("msb", "photo-page-2", "Two photos", "Deux photos"),
    ("msb", "photo-page-3", "Three photos", "Trois photos"),
    ("msb", "photo-page-4", "Four photos", "Quatre photos"),
    ("complex", "complex-photo-1", "One photo", "Une photo"),
    ("complex", "complex-photo-2", "Two photos", "Deux photos"),
    ("complex", "complex-photo-3", "Three photos", "Trois photos"),
    ("complex", "complex-photo-4", "Four photos", "Quatre photos"),
    ("complex", "complex-photo-5", "Five photos", "Cinq photos"),
]
AUTOMATIC_NAMES = [
    ("msb", "msb-orientation-1-2", "Automatic mode — 1 to 2 photos", "Mode automatique — 1 à 2 photos"),
    ("msb", "msb-orientation-1-2-3", "Automatic mode — 1 to 3 photos", "Mode automatique — 1 à 3 photos"),
    ("complex", "complex-auto-1-5", "Automatic mode — 1 to 5 photos", "Mode automatique — 1 à 5 photos"),
]


@pytest.fixture(autouse=True)
def isolated_activation(monkeypatch):
    # Activation replaces global dictionaries; restore the previous active set.
    for module, attribute in (
        (discovery, "_active_packs"),
        (translations, "_PACK_CATALOGS"),
        (translations, "_TEMPLATE_PACKS"),
        (template_extension_registry, "_extensions"),
    ):
        monkeypatch.setattr(module, attribute, getattr(module, attribute).copy())


@pytest.fixture
def packs():
    packs = discovery.discover_template_packs()
    discovery.replace_active_template_packs(packs)
    return {pack.pack_id: pack for pack in packs}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("language", ["en", "fr"])
@pytest.mark.parametrize("pack_id,template_id,english,french", ORDINARY_NAMES)
def test_all_ordinary_names(packs, language, pack_id, template_id, english, french):
    pack = packs[pack_id]
    template = next(item for item in pack.templates if item.template_id == template_id)
    name = english if language == "en" else french
    assert template_display_name(template, Translator(language)) == f"{pack.name} — {name}"


@pytest.mark.parametrize("language", ["en", "fr"])
@pytest.mark.parametrize("pack_id,mode_id,english,french", AUTOMATIC_NAMES)
def test_all_automatic_names(packs, language, pack_id, mode_id, english, french):
    pack = packs[pack_id]
    mode = next(item for item in pack.automatic_photo_page_modes if item.mode_id == mode_id)
    name = english if language == "en" else french
    assert automatic_photo_page_mode_display_name(mode, Translator(language)) == f"{pack.name} — {name}"


@pytest.mark.parametrize("pack_id", ["msb", "complex"])
def test_manifest_has_only_english_fallbacks_and_catalogs_cover_every_model(packs, pack_id):
    pack = packs[pack_id]
    manifest = json.loads((pack.path / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["templates"] + manifest["automatic_photo_page_modes"]:
        assert "localized_names" not in entry
        assert entry["name"] == pack.translation_catalogs["en"][f"template.{entry['id']}"]
        for language in ("en", "fr"):
            name = pack.translation_catalogs[language][f"template.{entry['id']}"]
            assert pack.name not in name
    assert {item.template_id for item in pack.templates} == {
        template_id for owner, template_id, _, _ in ORDINARY_NAMES if owner == pack_id
    }
    assert {item.mode_id for item in pack.automatic_photo_page_modes} == {
        mode_id for owner, mode_id, _, _ in AUTOMATIC_NAMES if owner == pack_id
    }


@pytest.mark.parametrize("language", ["de", "fr-FR", "fr_FR"])
@pytest.mark.parametrize("pack_id", ["msb", "complex"])
def test_catalog_language_and_english_fallback(packs, language, pack_id):
    pack = packs[pack_id]
    translator = Translator(language)
    catalog = pack.translation_catalogs["en" if language == "de" else "fr"]
    for template in pack.templates:
        assert template_display_name(template, translator) == f"{pack.name} — {catalog[f'template.{template.template_id}']}"
    for mode in pack.automatic_photo_page_modes:
        assert automatic_photo_page_mode_display_name(mode, translator) == f"{pack.name} — {catalog[f'template.{mode.mode_id}']}"


@pytest.mark.parametrize("localized,language,expected", [
    ({"fr": "Ancien nom", "en": "Legacy name"}, "fr", "Ancien nom"),
    ({"en": "Legacy name"}, "fr", "Legacy name"),
    ({}, "fr", "English fallback"),
])
def test_legacy_manifest_names_and_missing_catalogs(localized, language, expected):
    discovery.replace_active_template_packs(())
    template = TemplateDefinition(
        "legacy-photo", "English fallback", frozenset({TemplateKind.PHOTO_PAGE}), 1,
        pack_id="legacy", pack_name="Legacy", localized_names=localized,
    )
    mode = AutomaticPhotoPageModeDefinition(
        "legacy-auto", "English fallback", "legacy", "Legacy",
        (template.template_id,), template.template_id, localized_names=localized,
    )
    assert template_display_name(template, Translator(language)) == f"Legacy — {expected}"
    assert automatic_photo_page_mode_display_name(mode, Translator(language)) == f"Legacy — {expected}"


def test_automatic_labels_follow_pack_activation(packs):
    pack = packs["complex"]
    mode = pack.automatic_photo_page_modes[0]
    key = f"template.{mode.mode_id}"
    discovery.replace_active_template_packs((replace(
        pack, translation_catalogs={"en": {key: "Pack English"}, "fr": {key: "Nom du pack"}},
    ),))
    assert automatic_photo_page_mode_display_name(mode, Translator("fr")) == "Complex — Nom du pack"
    assert automatic_photo_page_mode_display_name(mode, Translator("de")) == "Complex — Pack English"
    discovery.replace_active_template_packs(())
    assert automatic_photo_page_mode_display_name(mode, Translator("fr")) == f"Complex — {mode.name}"


@pytest.mark.parametrize("language", ["en", "fr"])
def test_gui_lists_all_models_with_one_pack_prefix(app, packs, language):
    registry = discovery.create_template_registry()
    widget = AlbumSettingsWidget(registry, translator=Translator(language))
    try:
        labels = {
            combo.itemData(index): combo.itemText(index)
            for combo in widget.findChildren(QComboBox)
            for index in range(combo.count()) if isinstance(combo.itemData(index), str)
        }
        for pack_id, template_id, english, french in ORDINARY_NAMES + AUTOMATIC_NAMES:
            name = english if language == "en" else french
            assert labels[template_id] == f"{packs[pack_id].name} — {name}"
    finally:
        widget.close()


@pytest.mark.parametrize("language,expected", [("en", "Two photos"), ("fr", "Deux photos")])
@pytest.mark.parametrize("pack_id,template_id", [("msb", "photo-page-2"), ("complex", "complex-photo-2")])
def test_page_settings_title_uses_the_same_label(app, packs, language, expected, pack_id, template_id):
    template = next(item for item in packs[pack_id].templates if item.template_id == template_id)
    dialog = PageInstanceDialog(
        PageInstance(template_id), (), translator=Translator(language), template=template,
    )
    try:
        assert dialog._template_name() == f"{packs[pack_id].name} — {expected}"
    finally:
        dialog.close()


@pytest.mark.parametrize("language", ["en", "fr"])
def test_complex_caption_settings_have_their_own_translations(packs, language):
    catalog = packs["complex"].translation_catalogs[language]
    for suffix in (
        "page_section", "caption_group", "caption_show_user", "caption_show_datetime",
        "caption_show_location", "caption_font_family", "caption_font_size",
        "caption_color", "caption_choose_color", "caption_layout", "caption_order_user",
        "caption_order_datetime", "caption_order_location", "caption_order_break",
    ):
        assert catalog[f"page_settings.{suffix}"]
