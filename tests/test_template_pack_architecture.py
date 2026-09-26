"""Pack contracts exercised through discovery, activation and the album GUI."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import subprocess
from types import ModuleType

import pytest
from PySide6.QtWidgets import QApplication

from photoalbum.album import CoverPosition, TemplateRegistry
from photoalbum.album.composition import TemplateLayoutRegistry
from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.i18n import Translator
from photoalbum.template_engine import discovery
from photoalbum.template_engine.defaults import DEFAULT_TEMPLATE_PACK
from photoalbum.template_engine.extensions import (
    PageTemplateExtension, register_template_extension, template_extension_registry,
)
from photoalbum.template_engine.translations import translator_for_template


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def restore_activation(monkeypatch):
    packs = discovery.discover_template_packs()
    yield
    monkeypatch.undo()
    discovery.register_discovered_template_extensions(packs)


def selected_templates(settings):
    return [settings.covers[position].template_id for position in CoverPosition] + [
        settings.photo_pages.template_id,
        settings.year_dividers.template_id,
        settings.month_dividers.template_id,
        settings.day_dividers.template_id,
    ]


EXPECTED_DEFAULTS = [
    "year-photo-scatter", "geographic-word-cloud", "dedication",
    "geographic-word-cloud", "photo-page-2", "calendar-index", "month-divider-classic", "day-divider-simple",
]


@pytest.mark.parametrize("include_simplex", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("extra_id", ["aaa", "zzz"])
def test_msb_defaults_ignore_discovery_and_alphabetical_order(
    app, tmp_path, monkeypatch, include_simplex, reverse, extra_id,
):
    for pack in discovery.discover_template_packs():
        if pack.pack_id == 'simplex' and not include_simplex:
            continue
        directory = tmp_path / pack.pack_id
        directory.mkdir()
        (directory / 'manifest.json').write_text((pack.path / 'manifest.json').read_text())
    directory = tmp_path / extra_id
    directory.mkdir()
    (directory / 'manifest.json').write_text(json.dumps({
        'schema_version': 1, 'id': extra_id, 'name': extra_id,
        'templates': [{'id': extra_id, 'name': extra_id, 'module': 'unused_backend',
                       'kinds': ['cover', 'special_page', 'photo_page',
                                 'month_divider', 'year_divider', 'day_divider'], 'photo_capacity': 1}],
    }))
    paths = discovery._manifest_paths(tmp_path)
    if reverse:
        paths.reverse()
    monkeypatch.setattr(discovery, '_builtin_templates_root', lambda: tmp_path)
    monkeypatch.setattr(discovery, '_manifest_paths', lambda root: paths)
    registry = discovery.create_template_registry()
    widget = AlbumSettingsWidget(registry)
    try:
        assert DEFAULT_TEMPLATE_PACK == 'msb'
        assert selected_templates(widget.settings()) == EXPECTED_DEFAULTS
        assert all(registry.get(t).pack_id == DEFAULT_TEMPLATE_PACK for t in EXPECTED_DEFAULTS)
        widget._front_cover_combo.setCurrentIndex(widget._front_cover_combo.findData(extra_id))
        widget.reset_to_defaults()
        assert selected_templates(widget.settings()) == EXPECTED_DEFAULTS
    finally:
        widget.close()


def test_absent_msb_reports_missing_default_pack(app):
    simplex = next(p for p in discovery.discover_template_packs() if p.pack_id == 'simplex')
    registry = TemplateRegistry(list(simplex.templates))
    assert not registry.album_page_available(210, 297)
    with pytest.raises(ValueError, match="Default template pack 'msb' is missing"):
        AlbumSettingsWidget(registry)


def test_invalid_msb_still_fails_discovery(tmp_path):
    pack = tmp_path / 'msb'
    pack.mkdir()
    (pack / 'manifest.json').write_text('{"schema_version": -1}')
    with pytest.raises(ValueError, match='Unsupported template manifest schema'):
        discovery.discover_templates(tmp_path)


def test_removal_and_rediscovery_replace_all_active_capabilities(restore_activation):
    packs = discovery.register_discovered_template_extensions()
    msb = next(p for p in packs if p.pack_id == 'msb')
    simplex = next(p for p in packs if p.pack_id == 'simplex')
    discovery.register_discovered_template_extensions((simplex,))
    assert template_extension_registry.get('year-photo-scatter') is None
    assert discovery.pack_settings_editor('msb') is None
    assert discovery.pack_settings_editor('simplex') is None
    assert translator_for_template('year-photo-scatter', Translator('fr')).tr('msb_theme.title') == 'msb_theme.title'
    layouts = TemplateLayoutRegistry()
    discovery.register_discovered_layouts(layouts, (simplex,))
    with pytest.raises(KeyError, match='photo-page-2'):
        layouts.get('photo-page-2')

    discovery.register_discovered_template_extensions((msb,))
    assert template_extension_registry.get('simplex-full-photo-cover') is None
    assert discovery.pack_settings_editor('msb') is not None
    discovery.register_discovered_layouts(layouts, (msb,))
    assert layouts.get('photo-page-2') is not None
    discovery.register_discovered_template_extensions(())
    assert template_extension_registry.get('year-photo-scatter') is None
    discovery.register_discovered_template_extensions(packs)
    assert template_extension_registry.get('simplex-full-photo-cover') is not None


@pytest.mark.parametrize('failure', ['missing_module', 'missing_register', 'duplicate', 'undeclared'])
def test_invalid_extensions_do_not_replace_active_set(monkeypatch, restore_activation, failure):
    packs = discovery.register_discovered_template_extensions()
    previous = template_extension_registry.get('year-photo-scatter')
    module = ModuleType('arbitrary_backend')
    if failure != 'missing_module':
        monkeypatch.setitem(sys.modules, module.__name__, module)
    if failure in {'duplicate', 'undeclared'}:
        def register():
            template_id = packs[0].templates[0].template_id if failure == 'duplicate' else 'not-declared'
            register_template_extension(PageTemplateExtension(template_id))
            if failure == 'duplicate':
                register_template_extension(PageTemplateExtension(template_id))
        module.register = register
    invalid = replace(packs[0], modules=(module.__name__,))
    error = ModuleNotFoundError if failure == 'missing_module' else ValueError
    with pytest.raises(error):
        discovery.register_discovered_template_extensions((invalid,))
    assert template_extension_registry.get('year-photo-scatter') is previous
    assert discovery.pack_settings_editor('msb') is not None
    assert translator_for_template('year-photo-scatter', Translator('fr')).tr('msb_theme.title') == 'Thème MSB'


def test_collisions_fail_before_importing_modules(monkeypatch, restore_activation):
    packs = discovery.discover_template_packs()
    colliding = replace(packs[1], templates=(packs[0].templates[0],))
    monkeypatch.setattr(discovery, 'import_module', lambda name: pytest.fail('Imported before validation'))
    for pair in ((packs[0], packs[0]), (packs[0], colliding)):
        with pytest.raises(ValueError, match='Duplicate'):
            discovery.register_discovered_template_extensions(pair)
        with pytest.raises(ValueError, match='Duplicate'):
            discovery.register_discovered_layouts(TemplateLayoutRegistry(), pair)


@pytest.mark.parametrize('reference', [None, 'missing_options:edit', 'bad_options:edit'])
def test_editor_is_optional_lazy_and_validated(monkeypatch, restore_activation, reference):
    pack = replace(discovery.discover_template_packs()[0], settings_editor=reference)
    module = ModuleType('bad_options')
    module.edit = 12
    monkeypatch.setitem(sys.modules, module.__name__, module)
    discovery.replace_active_template_packs((pack,))
    if reference is None:
        assert discovery.pack_settings_editor(pack.pack_id) is None
    else:
        error = ModuleNotFoundError if reference.startswith('missing') else ValueError
        with pytest.raises(error):
            discovery.pack_settings_editor(pack.pack_id)


@pytest.mark.parametrize('reference', ['', 12, {}, 'module', ':edit', 'module:'])
def test_invalid_editor_metadata_is_rejected(tmp_path, reference):
    pack = tmp_path / 'example'
    pack.mkdir()
    manifest = pack / 'manifest.json'
    manifest.write_text(json.dumps({
        'schema_version': 1, 'id': 'example', 'name': 'Example',
        'settings_editor': reference, 'templates': [],
    }))
    with pytest.raises(ValueError, match='settings_editor'):
        discovery.load_template_pack(manifest)


def test_core_and_packs_have_no_internal_import_coupling():
    root = Path(discovery.__file__).parents[1]
    forbidden = (
        'photoalbum.templates.', 'scatter', 'calendar_index', 'geographic_word_cloud',
        'full_photo_cover', 'photo_caption"', 'banana_density',
        'PhotoCaptionSettings', 'PhotoTemplateLayout', 'month_divider_classic',
    )
    for path in root.rglob('*.py'):
        if 'templates' not in path.relative_to(root).parts:
            text = path.read_text()
            assert not any(word in text for word in forbidden), path
            if path.name != 'defaults.py':
                assert 'msb' not in text.lower() and 'simplex' not in text.lower(), path
    for name, other in [('msb', 'simplex'), ('simplex', 'msb')]:
        for path in (root / 'templates' / name).rglob('*.py'):
            assert other not in path.read_text().lower(), path


def test_default_roles_are_owned_by_manifest(app, monkeypatch):
    packs = discovery.discover_template_packs()
    changed = tuple(replace(p, default_templates={**p.default_templates,
                    'front_cover': 'geographic-word-cloud'}) if p.pack_id == 'msb' else p
                    for p in packs)
    monkeypatch.setattr(discovery, 'discover_template_packs', lambda root=None: changed)
    widget = AlbumSettingsWidget(discovery.create_template_registry())
    assert widget.settings().covers[CoverPosition.FRONT].template_id == 'geographic-word-cloud'
    widget.close()


@pytest.mark.parametrize('roles', [[], {'unknown': 'photo-page-2'},
                                  {'front_cover': 'simplex-full-photo-cover'},
                                  {'front_cover': 'photo-page-2'}])
def test_invalid_default_roles_fail_discovery(tmp_path, roles):
    pack = next(p for p in discovery.discover_template_packs() if p.pack_id == 'msb')
    data = json.loads((pack.path / 'manifest.json').read_text())
    data['default_templates'] = roles
    path = tmp_path / 'msb/manifest.json'
    path.parent.mkdir()
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        discovery.load_template_pack(path)


@pytest.mark.parametrize('pack_id,blocked_id', [('msb', 'simplex'), ('simplex', 'msb')])
def test_pack_loads_in_fresh_process_without_the_other(pack_id, blocked_id):
    script = '''
import importlib.abc
import sys
class BlockOtherPack(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == sys.argv[2] or fullname.startswith(sys.argv[2] + '.'):
            raise AssertionError('Imported the other pack: ' + fullname)
sys.meta_path.insert(0, BlockOtherPack())
from photoalbum.template_engine.discovery import (
    discover_template_packs, register_discovered_template_extensions,
    register_discovered_layouts, pack_settings_editor,
)
from photoalbum.album.composition import TemplateLayoutRegistry
from photoalbum.template_engine import template_extension_registry
pack = next(p for p in discover_template_packs() if p.pack_id == sys.argv[1])
register_discovered_template_extensions((pack,))
register_discovered_layouts(TemplateLayoutRegistry(), (pack,))
pack_settings_editor(pack.pack_id)
assert all(template_extension_registry.get(t.template_id) for t in pack.templates)
'''
    subprocess.run(
        [sys.executable, '-c', script, pack_id, f'photoalbum.templates.{blocked_id}'],
        check=True, capture_output=True, text=True,
    )


def test_discovery_rejects_duplicate_template_ids(tmp_path):
    for pack_id in ('first', 'second'):
        directory = tmp_path / pack_id
        directory.mkdir()
        (directory / 'manifest.json').write_text(json.dumps({
            'schema_version': 1, 'id': pack_id, 'name': pack_id,
            'templates': [{'id': 'collision', 'name': 'Collision', 'module': 'unused',
                           'kinds': ['special_page']}],
        }))
    with pytest.raises(ValueError, match='already registered: collision'):
        discovery.discover_templates(tmp_path)


@pytest.mark.parametrize('failure', ['missing_module', 'invalid_hook', 'duplicate_layout'])
def test_invalid_layout_declarations(monkeypatch, failure):
    module = ModuleType('layout_backend')
    if failure != 'missing_module':
        monkeypatch.setitem(sys.modules, module.__name__, module)
    if failure == 'invalid_hook':
        module.register_layouts = 42
    elif failure == 'duplicate_layout':
        def register_layouts(registry):
            registry.register('photo-page-2', object())
            registry.register('photo-page-2', object())
        module.register_layouts = register_layouts
    pack = replace(discovery.discover_template_packs()[0], modules=(module.__name__,))
    error = ModuleNotFoundError if failure == 'missing_module' else ValueError
    with pytest.raises(error):
        discovery.register_discovered_layouts(TemplateLayoutRegistry(), (pack,))
