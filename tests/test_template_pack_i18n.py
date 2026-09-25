import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile
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


def test_built_distributions_include_pack_catalogs(tmp_path):
    from tests.pack_lifecycle_support import FIXTURES, run_pack_lifecycle

    source = tmp_path / 'build_source'
    source.mkdir()
    for name in ('pyproject.toml', 'README.md', 'LICENSE'):
        shutil.copy2(name, source / name)
    shutil.copytree('src', source / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
    shutil.copytree(FIXTURES / 'template_packs/testpack', source / 'src/photoalbum/templates/testpack')
    subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(tmp_path)],
        check=True,
        cwd=source,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    sdist = next(tmp_path.glob("*.tar.gz"))
    expected = {
        "photoalbum/templates/msb/i18n/en.json",
        "photoalbum/templates/msb/i18n/fr.json",
        "photoalbum/templates/simplex/i18n/en.json",
        "photoalbum/templates/simplex/i18n/fr.json",
        "photoalbum/templates/msb/manifest.json",
        "photoalbum/templates/simplex/manifest.json",
        "photoalbum/templates/msb/docs/developer.md",
        "photoalbum/templates/simplex/docs/developer.md",
        "photoalbum/templates/msb/month_divider_classic/layout.py",
        "photoalbum/templates/msb/year_photo_scatter/render_worker.py",
        "photoalbum/templates/msb/photo_page/composition.py",
        "photoalbum/templates/testpack/manifest.json",
        "photoalbum/templates/testpack/components.py",
        "photoalbum/templates/testpack/assets/palette.json",
        "photoalbum/templates/testpack/i18n/fr.json",
    }
    with zipfile.ZipFile(wheel) as archive:
        assert expected <= set(archive.namelist())
        assert 'photoalbum/album/month_divider_layout.py' not in archive.namelist()
        assert 'photoalbum/rendering/cover_render_worker.py' not in archive.namelist()
    with tarfile.open(sdist) as archive:
        names = {name.split("/", 1)[-1] for name in archive.getnames()}
        assert {f"src/{name}" for name in expected} <= names

    installed = tmp_path / 'installed'
    subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--no-deps', '--no-index',
         '--target', str(installed), str(wheel)],
        check=True, capture_output=True, text=True,
    )
    # Isolated interpreter outside the checkout, loading the installed wheel.
    # Dependencies come from the test environment, not from another install.
    smoke = '''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import photoalbum
assert Path(photoalbum.__file__).is_relative_to(Path(sys.argv[1]))
from PySide6.QtWidgets import QApplication
from photoalbum.template_engine.discovery import (
    discover_templates, register_discovered_template_extensions,
    register_discovered_layouts, pack_settings_editor,
)
from photoalbum.template_engine import translator_for_template, template_extension_registry
from photoalbum.album.composition import TemplateLayoutRegistry
from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.i18n import Translator
app = QApplication([])
found = discover_templates()
assert {p.pack_id for p in found.packs} == {'msb', 'simplex', 'testpack'}
register_discovered_template_extensions(found.packs)
layouts = TemplateLayoutRegistry()
register_discovered_layouts(layouts, found.packs)
assert layouts.get('photo-page-2')
assert callable(pack_settings_editor('msb'))
assert pack_settings_editor('simplex') is None
assert template_extension_registry.preview_backend('year-photo-scatter') is not None
assert template_extension_registry.widget_renderer('simplex-full-photo-cover') is not None
assert translator_for_template('year-photo-scatter', Translator('fr')).tr('msb_theme.title') == 'Thème MSB'
assert translator_for_template('simplex-full-photo-cover', Translator('fr')).tr('simplex.full-photo-cover.source') == 'Source de l’image'
for pack in found.packs:
    assert pack.documentation_path('fr').is_file()
    assert pack.path.is_relative_to(Path(sys.argv[1]))
for name, module in tuple(sys.modules.items()):
    if name.startswith('photoalbum.') and getattr(module, '__file__', None):
        assert Path(module.__file__).is_relative_to(Path(sys.argv[1])), name
widget = AlbumSettingsWidget(found.registry)
assert widget.settings().photo_pages.template_id == 'photo-page-2'
widget.close()
'''
    subprocess.run(
        [sys.executable, '-I', '-c', smoke, str(installed)],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    run_pack_lifecycle(installed, tmp_path)
