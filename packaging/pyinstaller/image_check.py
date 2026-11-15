"""Run inside both frozen executables, without a development Python fallback."""
from dataclasses import replace
from datetime import datetime
from pathlib import Path


def check_image(fixture: Path, output: Path) -> None:
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QApplication
    from pypdf import PdfReader
    from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
    from photoalbum.album import AlbumBuilder
    from photoalbum.export import PdfExportService
    from photoalbum.i18n import Translator
    from photoalbum.images import decode_image
    from photoalbum.metadata import PhotoAnalyzer
    from photoalbum.rendering.image_cache import RenderImageCache
    from photoalbum.template_engine import create_template_registry, register_discovered_template_extensions

    application = QApplication.instance() or QApplication([])
    original = fixture.read_bytes()
    photo = PhotoAnalyzer().analyze(fixture)
    assert (photo.width, photo.height) == (64, 96)
    assert photo.capture_datetime == datetime(2024, 6, 15, 12, 34, 56)
    assert (photo.latitude, photo.longitude) == (48.5, -2.25)
    with decode_image(fixture) as image:
        assert image.size == (64, 96)
        r, g, b = image.getpixel((16, 24))
        assert b > 180 and r < 80 and g < 100, (r, g, b)
    pixmap = RenderImageCache().load(fixture, QSize(96, 96))
    assert pixmap.size() == QSize(64, 96)
    assert pixmap.toImage().pixelColor(16, 24).blue() > 180
    register_discovered_template_extensions()
    registry = create_template_registry()
    editor = AlbumSettingsWidget(registry)
    try:
        settings = editor.settings()
    finally:
        editor.close()
    settings.month_dividers = replace(settings.month_dividers, enabled=False)
    settings.year_dividers = replace(settings.year_dividers, enabled=False)
    result = AlbumBuilder(registry).build([photo], settings)
    PdfExportService(Translator("en")).export(
        output_path=output, result=result, settings=settings, photos=[photo],
        page_width_mm=100, page_height_mm=150, dpi=72,
    )
    reader = PdfReader(output)
    images = [image.image for page in reader.pages for image in page.images]
    assert images, "The exported PDF contains no image"
    portrait_images = [im for im in images if im.height > im.width]
    assert portrait_images, "The exported PDF lost the photo's orientation"
    for image in portrait_images:
        r, g, b = image.convert("RGB").getpixel((image.width // 4, image.height // 4))
        assert b > 170 and r < 90 and g < 110, (r, g, b)
    assert fixture.read_bytes() == original
    application.processEvents()


def main() -> int:
    import sys
    check_image(Path(sys.argv[2]), Path(sys.argv[3]))
    return 0
