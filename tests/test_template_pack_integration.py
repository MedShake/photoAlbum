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
    pack = tmp_path / 'independent'
    pack.mkdir()
    (pack / 'editor_backend.py').write_text('''
def edit_settings(settings, *, translator, parent=None):
    assert translator.tr("probe") == "Translated probe"
    return {**settings, "independent": {"color": "blue"}}
''')
    (pack / 'paint_backend.py').write_text('''
from photoalbum.template_engine.api import (
    NormalizedRect, PageComposition, PhotoSlotComposition,
    PageTemplateExtension, register_template_extension,
    TemplatePreviewBackend, PreviewJob,
)

from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtGui import QPixmap

calls = []

class Signals(QObject):
    finished = Signal(str, bytes)
    failed = Signal(str, str)

class Worker(QRunnable):
    def __init__(self, request_id):
        super().__init__()
        self.request_id = request_id
        self.signals = Signals()

    def run(self):
        self.signals.finished.emit(self.request_id, b"preview")

class Preview(TemplatePreviewBackend):
    template_id = "independent-cover"

    def create_job(self, *, request_id, translator, **kwargs):
        assert translator.tr("probe") == "Translated probe"
        def finalize(data):
            assert data == b"preview"
            pixmap = QPixmap(10, 10)
            pixmap.fill(0xFF123456)
            return pixmap
        return PreviewJob(worker=Worker(request_id), finalize=finalize)

class Renderer:
    def paint(self, *, painter, target_rect, translator, template_pack_settings=None, **kwargs):
        assert translator.tr("probe") == "Translated probe"
        calls.append(template_pack_settings)
        painter.fillRect(target_rect, 0xFF123456)

def register():
    register_template_extension(PageTemplateExtension(
        template_id="independent-photo", widget_renderer=Renderer()))
    register_template_extension(PageTemplateExtension(
        template_id="independent-cover", widget_renderer=Renderer(), preview_backend=Preview()))

class Layout:
    def compose(self, page, settings, page_numbers, **kwargs):
        return PageComposition(page=page, photo_slots=(PhotoSlotComposition(
            image_rect=NormalizedRect(.1, .2, .8, .6), caption_rect=None, caption=None),))

def register_layouts(registry):
    registry.register("independent-photo", Layout())
''')
    (pack / 'manifest.json').write_text(json.dumps({
        'schema_version': 1, 'id': 'independent', 'name': 'Independent', 'version': '1',
        'settings_editor': 'editor_backend:edit_settings',
        'templates': [
            {'id': 'independent-photo', 'name': 'Photo', 'module': 'paint_backend',
             'kinds': ['photo_page'], 'photo_capacity': 1},
            {'id': 'independent-cover', 'name': 'Cover', 'module': 'paint_backend',
             'kinds': ['cover']},
        ],
    }))
    (pack / 'i18n').mkdir()
    (pack / 'i18n/en.json').write_text(json.dumps({
        'probe': 'Translated probe',
        'template.independent-photo': 'Translated photo',
    }))
    monkeypatch.syspath_prepend(str(pack))
    # Keep global executable extensions isolated from other tests.
    monkeypatch.setattr(template_extension_registry, '_extensions', dict(template_extension_registry._extensions))
    original_packs = discovery.discover_template_packs()
    registry = discovery.create_template_registry()
    previous = template_extension_registry.get("year-photo-scatter")
    discovered = discovery.discover_templates(tmp_path)
    assert "paint_backend" not in sys.modules
    assert "editor_backend" not in sys.modules
    assert template_extension_registry.get("year-photo-scatter") is previous
    for definition in discovered.registry.list_all():
        registry.register(definition)
    discovery.register_discovered_template_extensions(discovered.packs)
    monkeypatch.setattr(discovery, '_builtin_templates_root', lambda: tmp_path)
    try:
        yield registry, discovered.packs, importlib.import_module('paint_backend')
    finally:
        discovery.register_discovered_template_extensions(original_packs)
        for name in tuple(sys.modules):
            if name in {'paint_backend', 'editor_backend'}:
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


def test_declared_pack_label_and_async_preview(external_pack):
    from time import monotonic
    from PySide6.QtTest import QTest
    from photoalbum.album import PageInstance
    from photoalbum.gui.preview_render_service import PreviewRenderService
    from photoalbum.gui.template_labels import template_display_name

    app = QApplication.instance() or QApplication([])
    registry, _, _ = external_pack
    assert template_display_name(registry.get('independent-photo'), Translator('fr')) == (
        'Independent — Translated photo'
    )
    service = PreviewRenderService(Translator('fr'))
    received = []
    service.preview_ready.connect(received.append)
    key = service.request(
        PageInstance(template_id='independent-cover'), (),
        width=100, height=100, page_width_mm=210, page_height_mm=297,
    )
    deadline = monotonic() + 5
    while not received and monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert received == [key]


def test_removed_manifest_then_rediscovered_pack(external_pack):
    from photoalbum.template_engine import translator_for_template

    _, packs, _ = external_pack
    manifest = packs[0].path / 'manifest.json'
    content = manifest.read_text()
    manifest.unlink()
    found = discovery.discover_templates()
    assert found.packs == ()
    # Discovery alone leaves active behavior untouched.
    assert discovery.pack_settings_editor('independent') is not None
    discovery.register_discovered_template_extensions(found.packs)
    assert discovery.pack_settings_editor('independent') is None
    assert template_extension_registry.get('independent-photo') is None
    assert translator_for_template('independent-photo', Translator('en')).tr('probe') == 'probe'
    manifest.write_text(content)
    found = discovery.discover_templates()
    discovery.register_discovered_template_extensions(found.packs)
    assert discovery.pack_settings_editor('independent') is not None
    assert template_extension_registry.preview_backend('independent-cover') is not None
    assert translator_for_template('independent-photo', Translator('fr')).tr('probe') == 'Translated probe'
    layouts = TemplateLayoutRegistry()
    discovery.register_discovered_layouts(layouts, found.packs)
    assert layouts.get('independent-photo') is not None


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
