"""A pack added as a directory must work without application edits."""
import importlib
import json
import sys
from dataclasses import replace
from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter
from pypdf import PdfReader

from photoalbum.album import AlbumBuilder, CoverPosition, CoverSettings, PhotoPageSettings
from photoalbum.album.composition import PageComposer, TemplateLayoutRegistry
from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.template_engine import discovery
from photoalbum.template_engine.extensions import template_extension_registry


@pytest.fixture
def external_pack(tmp_path, monkeypatch):
    import photoalbum.templates

    pack = tmp_path / 'independent'
    pack.mkdir()
    (pack / '__init__.py').write_text('''
def edit_settings(settings, *, translator, parent=None):
    return {**settings, "independent": {"color": "blue"}}
''')
    (pack / 'page.py').write_text('''
from photoalbum.album.composition import NormalizedRect, PhotoTemplateLayout
from photoalbum.template_engine.extensions import PageTemplateExtension, register_template_extension

calls = []

class Renderer:
    def paint(self, *, painter, target_rect, template_pack_settings=None, **kwargs):
        calls.append(template_pack_settings)
        painter.fillRect(target_rect, 0xFF123456)

def register():
    register_template_extension(PageTemplateExtension(
        template_id="independent-photo", widget_renderer=Renderer()))
    register_template_extension(PageTemplateExtension(
        template_id="independent-cover", widget_renderer=Renderer()))

def register_layouts(registry):
    registry.register("independent-photo", PhotoTemplateLayout(
        cells_factory=lambda width, height: (NormalizedRect(.1, .2, .8, .6),)))
''')
    (pack / 'manifest.json').write_text(json.dumps({
        'schema_version': 1, 'id': 'independent', 'name': 'Independent', 'version': '1',
        'templates': [
            {'id': 'independent-photo', 'name': 'Photo', 'module': 'page',
             'kinds': ['photo_page'], 'photo_capacity': 1},
            {'id': 'independent-cover', 'name': 'Cover', 'module': 'page',
             'kinds': ['cover']},
        ],
    }))
    monkeypatch.setattr(photoalbum.templates, '__path__', [*photoalbum.templates.__path__, str(tmp_path)])
    # Keep global executable extensions isolated from other tests.
    monkeypatch.setattr(template_extension_registry, '_extensions', dict(template_extension_registry._extensions))
    registry = discovery.create_template_registry()
    discovered = discovery.discover_templates(tmp_path)
    for definition in discovered.registry.list_all():
        registry.register(definition)
    discovery.register_discovered_template_extensions(discovered.packs)
    monkeypatch.setattr(discovery, '_builtin_templates_root', lambda: tmp_path)
    try:
        yield registry, discovered.packs, importlib.import_module('photoalbum.templates.independent.page')
    finally:
        for name in tuple(sys.modules):
            if name.startswith('photoalbum.templates.independent'):
                del sys.modules[name]


def test_directory_pack_composes_edits_settings_and_exports(external_pack, tmp_path):
    from photoalbum.export import PdfExportService

    app = QApplication.instance() or QApplication([])
    registry, packs, module = external_pack
    widget = AlbumSettingsWidget(registry)
    widget._template_pack_settings = {'msb': {'keep': True}}
    assert widget._open_pack_settings_dialog('independent-photo')
    assert widget._template_pack_settings == {'msb': {'keep': True}, 'independent': {'color': 'blue'}}

    settings = widget.settings()
    settings.photo_pages = PhotoPageSettings(template_id='independent-photo')
    settings.covers = {p: CoverSettings(position=p, template_id='independent-cover') for p in CoverPosition}
    settings.month_dividers = replace(settings.month_dividers, enabled=False)
    settings.year_dividers = replace(settings.year_dividers, enabled=False)
    photo = Photo(path=tmp_path / 'photo.jpg', filename='photo.jpg', capture_datetime=datetime(2025, 1, 2))
    result = AlbumBuilder(registry).build([photo], settings)
    page = next(p for p in result.pagination.pages if p.template_id == 'independent-photo')
    composition = PageComposer().compose(page, settings.photo_pages)
    assert len(composition.photo_slots) == 1
    assert composition.photo_slots[0].image_rect.x == .1
    assert composition.photo_slots[0].image_rect.width == .8

    from photoalbum.rendering import PageRenderer, PageRenderGeometry

    image = QImage(210, 297, QImage.Format.Format_ARGB32)
    geometry = PageRenderGeometry(width=210, height=297, page_width_mm=210, page_height_mm=297)
    painter = QPainter(image)
    try:
        PageRenderer(translator=Translator('en')).paint(
            painter=painter, composition=composition, target_rect=image.rect(),
            width=210, height=297, page_width_mm=210, page_height_mm=297,
            font_pixel_size=geometry.font_pixel_size, pixel_rect=geometry.pixel_rect,
            thumbnail_cache=None, template_pack_settings=settings.template_pack_settings,
        )
    finally:
        painter.end()
    assert image.pixelColor(100, 100).name() == '#123456'

    output = tmp_path / 'independent.pdf'
    PdfExportService(Translator('en')).export(
        output_path=output, result=result, settings=settings, photos=[photo],
        page_width_mm=210, page_height_mm=297, dpi=72,
    )
    assert len(PdfReader(output).pages) == result.total_page_count
    assert len(module.calls) == 6  # Preview, four covers, and the photo page.
    assert all(context == settings.template_pack_settings for context in module.calls)
    widget.close()


def test_missing_photo_layout_fails_before_rendering(external_pack, monkeypatch):
    _, packs, module = external_pack
    monkeypatch.delattr(module, 'register_layouts')
    with pytest.raises(KeyError, match='independent-photo'):
        discovery.register_discovered_layouts(TemplateLayoutRegistry(), packs)


def test_msb_theme_dialog_cancellation_and_acceptance(monkeypatch):
    from photoalbum.templates.msb import edit_settings
    from photoalbum.templates.msb.theme import MsbTheme, msb_theme_from_pack_settings
    from photoalbum.templates.msb.theme_dialog import MsbThemeDialog

    app = QApplication.instance() or QApplication([])
    original = {'other': {'keep': True}, 'msb': {'future': 42}}
    monkeypatch.setattr(MsbThemeDialog, 'exec', lambda self: 0)
    assert edit_settings(original, translator=Translator('en')) is None
    monkeypatch.setattr(MsbThemeDialog, 'exec', lambda self: 1)
    monkeypatch.setattr(MsbThemeDialog, 'theme', lambda self: MsbTheme(default_font_family='DejaVu Serif'))
    updated = edit_settings(original, translator=Translator('en'))
    assert updated['other'] == {'keep': True}
    assert updated['msb']['future'] == 42
    assert msb_theme_from_pack_settings(updated).default_font_family == 'DejaVu Serif'
    assert original == {'other': {'keep': True}, 'msb': {'future': 42}}
