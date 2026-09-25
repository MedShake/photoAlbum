"""Run in a fresh interpreter against either a copied source tree or a wheel."""
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from dataclasses import replace
from datetime import datetime
import shutil
from time import monotonic
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage, QPainter
from pypdf import PdfReader

from photoalbum.album import AlbumBuilder, CoverPosition, CoverSettings, PhotoPageSettings
from photoalbum.album.composition import PageComposer
from photoalbum.app import ProjectService
from photoalbum.export import PdfExportService
from photoalbum.gui.template_settings import create_template_settings_editor
from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.gui.widgets.album_preview_widget import AlbumCoverPreview, AlbumPagePreview
from photoalbum.gui.preview_render_service import PreviewRenderService
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.rendering import PageRenderer, PageRenderGeometry, RenderImageCache
from photoalbum.template_engine import (
    discover_templates, register_discovered_template_extensions, template_extension_registry,
    create_template_instance, translator_for_template,
)
from photoalbum.template_engine.discovery import pack_settings_editor

app = QApplication([])
translator = Translator("fr")
found = discover_templates()
assert "photoalbum.templates.testpack.components" not in sys.modules
register_discovered_template_extensions(found.packs)
from photoalbum.templates.testpack import components

widget = AlbumSettingsWidget(found.registry, translator=translator)
assert widget.settings().photo_pages.template_id == "photo-page-2"
assert widget._front_cover_combo.findText("Test Pack — Page banane") >= 0
widget._front_cover_combo.setCurrentIndex(widget._front_cover_combo.findData("testpack-page"))
instance = widget.settings().covers[CoverPosition.FRONT].page
assert instance.settings == components.defaults()
other = create_template_instance("testpack-page")
other.settings["nested"]["values"].append(99)
assert instance.settings["nested"]["values"] == [1, 2]

editor = create_template_settings_editor("testpack-page", instance, (), translator=translator)
assert editor.findChildren(components.QLabel)[0].text() == "Densité"
editor.density.setValue(23)
instance = editor.instance()
assert instance.settings["banana_density"] == 23
settings = widget.settings()
settings.covers = {p: CoverSettings(position=p, page=instance) for p in CoverPosition}
settings.photo_pages = PhotoPageSettings(page=instance)
settings.front_matter = [instance]
settings.month_dividers = replace(settings.month_dividers, enabled=False)
settings.year_dividers = replace(settings.year_dividers, enabled=False)
settings.template_pack_settings = pack_settings_editor("testpack")({}, translator=translator)

project = ProjectService()
project_path = Path(sys.argv[2]) / "opaque.photoalbum"
project.create(project_path)
project.set_album_structure_settings(settings)
project.close()
project.open(project_path)
restored = project.get_album_structure_settings()
assert restored == settings
project.close()

photo = Photo(path=Path(sys.argv[2]) / "image.jpg", filename="image.jpg", capture_datetime=datetime(2025, 2, 3))
result = AlbumBuilder(found.registry).build([photo], restored)
assert all(value["banana_density"] == 23 for value in components.layout_calls)
page = next(p for p in result.pagination.pages if p.photo_capacity)
composition = PageComposer().compose(page, restored.photo_pages)
assert composition.photo_slots[0].image_rect.x == .23
geometry = PageRenderGeometry(width=210, height=297, page_width_mm=210, page_height_mm=297)
image = QImage(210, 297, QImage.Format.Format_ARGB32)
painter = QPainter(image)
try:
    PageRenderer(translator=translator).paint(
        painter=painter, composition=composition, target_rect=image.rect(), width=210, height=297,
        page_width_mm=210, page_height_mm=297, font_pixel_size=geometry.font_pixel_size,
        pixel_rect=geometry.pixel_rect, thumbnail_cache=RenderImageCache(),
        template_pack_settings=restored.template_pack_settings,
    )
finally:
    painter.end()
assert image.pixelColor(1, 1).name() == "#654321"

service = PreviewRenderService(translator)
ready = []
service.preview_ready.connect(ready.append)
key = service.request(instance, (photo,), width=210, height=297, page_width_mm=210, page_height_mm=297)
deadline = monotonic() + 5
while not ready and monotonic() < deadline:
    app.processEvents()
    QTest.qWait(5)
assert ready == [key]
assert components.preview_calls[-1] == (instance.settings, "Bananes")

# Exercise the real cover widget in addition to the shared page renderer.
cover = AlbumCoverPreview(
    position=CoverPosition.FRONT, template_id=instance.template_id, registry=found.registry,
    result=result, cover_settings=restored.covers[CoverPosition.FRONT],
    thumbnail_cache=RenderImageCache(), page_format=restored.effective_page_format(),
    translator=translator, render_service=service,
    template_pack_settings=restored.template_pack_settings,
)
assert cover.grab().toImage().pixelColor(2, 2).name() == "#654321"
output = Path(sys.argv[2]) / "pack.pdf"
PdfExportService(translator).export(
    output_path=output, result=result, settings=restored, photos=[photo],
    page_width_mm=210, page_height_mm=297, dpi=72,
)
reader = PdfReader(output)
assert len(reader.pages) == result.total_page_count
assert all("Bananes" in page.extract_text() for page in reader.pages)
assert all(call == (instance.settings, "Bananes", restored.template_pack_settings)
           for call in components.render_calls)

invalid = replace(restored, photo_pages=PhotoPageSettings(
    page=instance.with_settings({"banana_density": -1}),
))
try:
    AlbumBuilder(found.registry).build([photo], invalid)
except ValueError as exc:
    assert "Invalid banana density" in str(exc)
else:
    raise AssertionError("Pack validation was not called")

# Physical removal and rediscovery, with no change to any core file.
pack_path = next(p.path for p in found.packs if p.pack_id == "testpack")
shutil.rmtree(pack_path)
remaining = discover_templates()
assert all(t.pack_id != "testpack" for t in remaining.registry.list_all())
register_discovered_template_extensions(remaining.packs)
assert template_extension_registry.get("testpack-page") is None
assert pack_settings_editor("testpack") is None
assert translator_for_template("testpack-page", translator).tr("banana.label") == "banana.label"
simplex_path = next(p.path for p in remaining.packs if p.pack_id == "simplex")
shutil.rmtree(simplex_path)
remaining = discover_templates()
register_discovered_template_extensions(remaining.packs)
assert {p.pack_id for p in remaining.packs} == {"msb"}
assert template_extension_registry.get("simplex-full-photo-cover") is None
assert AlbumSettingsWidget(remaining.registry).settings().photo_pages.template_id == "photo-page-2"
shutil.rmtree(remaining.packs[0].path)
empty = discover_templates()
register_discovered_template_extensions(empty.packs)
try:
    AlbumSettingsWidget(empty.registry)
except ValueError as exc:
    assert "Default template pack 'msb' is missing" in str(exc)
else:
    raise AssertionError("Missing default pack did not produce a clear error")
cover.close()
editor.close()
widget.close()
