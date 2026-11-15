"""Real HEVC fixtures through metadata, sources, GUI caches and PDF export."""
from dataclasses import replace
from datetime import datetime
from io import BytesIO
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time

import pytest
from PIL import Image, ImageCms, ImageOps
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication
from pypdf import PdfReader

from photoalbum.images import (
    SUPPORTED_EXTENSIONS, ExifReader, decode_image, image_glob_patterns,
    is_guaranteed_opaque, open_image,
)
from photoalbum.metadata import PhotoAnalyzer
from photoalbum.models.photo import displayed_photo_dimensions
from photoalbum.rendering.image_cache import RenderImageCache
from photoalbum.rendering.image_loader import load_qimage
from photoalbum.gui.preview_image_cache import PreviewImageCache
from photoalbum.gui.widgets.photo_places_widget import PhotoPlacesWidget
from photoalbum.i18n import Translator


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "images"
pattern = runpy.run_path(str(FIXTURES / "generate.py"))["pattern"]
TRANSFORMS = {
    2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM, 5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def assert_corners(actual, expected, tolerance=4):
    assert actual.size == expected.size
    for x in (actual.width // 4, actual.width * 3 // 4):
        for y in (actual.height // 4, actual.height * 3 // 4):
            assert actual.convert("RGB").getpixel((x, y)) == pytest.approx(
                expected.convert("RGB").getpixel((x, y)), abs=tolerance,
            )


@pytest.mark.parametrize("orientation", range(1, 9))
@pytest.mark.parametrize("extension", ["heic", "jpg", "tiff", "tif"])
def test_metadata_orientation_pixels_and_original_preservation(tmp_path, orientation, extension):
    path = tmp_path / f"photo.{extension}"
    if extension == "heic":
        shutil.copyfile(FIXTURES / f"orientation-{orientation}.heic", path)
    else:
        exif = Image.Exif()
        exif[274] = orientation
        if extension == "tif":
            # libtiff's encoder cannot write a nested EXIF IFD here.
            exif[306] = "2024:06:15 12:34:56"
        else:
            exif[34665] = {36867: "2024:06:15 12:34:56"}
        options = ({"quality": 100, "subsampling": 0} if extension == "jpg"
                   else {"compression": "raw" if extension == "tiff" else "tiff_lzw"})
        pattern().save(path, exif=exif.tobytes(), **options)
    original, stat = path.read_bytes(), path.stat()
    expected = pattern()
    if orientation != 1:
        expected = expected.transpose(TRANSFORMS[orientation])
    photo = PhotoAnalyzer().analyze(path)
    assert photo.capture_datetime == datetime(2024, 6, 15, 12, 34, 56)
    assert displayed_photo_dimensions(photo) == expected.size
    if extension == "heic":
        assert (photo.latitude, photo.longitude) == (48.5, -2.25)
        assert photo.orientation in (None, 1)  # container transforms already applied
    elif extension == "jpg":
        assert photo.orientation == orientation
    else:
        assert (photo.width, photo.height) == expected.size
        assert photo.orientation in (None, 1)  # Pillow has already oriented TIFF pixels
    with decode_image(path) as actual:
        assert_corners(actual, expected)
        assert actual.getexif().get(274) is None
    assert path.read_bytes() == original
    assert path.stat().st_mtime_ns == stat.st_mtime_ns
    assert list(tmp_path.iterdir()) == [path]


def test_real_heif_without_exif_uses_filename_date(tmp_path):
    path = tmp_path / "2020-02-03.HEIF"
    shutil.copyfile(FIXTURES / "no-exif.heif", path)
    metadata = ExifReader().read(path)
    assert (metadata.width, metadata.height) == (96, 64)
    assert metadata.capture_datetime is None
    assert metadata.latitude is None and metadata.longitude is None
    assert PhotoAnalyzer().analyze(path).capture_datetime == datetime(2020, 2, 3)


def test_registry_drives_scanning_and_dialog_patterns(tmp_path):
    from photoalbum.scanner import FolderScanner
    for extension in SUPPORTED_EXTENSIONS:
        (tmp_path / f"photo{extension.upper()}").touch()
    (tmp_path / "unsupported.gif").touch()
    assert len(FolderScanner().scan(tmp_path)) == len(SUPPORTED_EXTENSIONS)
    assert set(image_glob_patterns().split()) == {f"*{ext}" for ext in SUPPORTED_EXTENSIONS}
    assert is_guaranteed_opaque("PHOTO.JPEG")
    assert not is_guaranteed_opaque("alpha.heic")


@pytest.mark.parametrize("budget,fit,expected", [
    ((24, 24), "contain", (16, 24)), ((24, 24), "cover", (24, 36)),
    ((400, 400), "contain", (64, 96)), ((400, 400), "cover", (64, 96)),
])
def test_oriented_pixel_budget_without_upsampling(budget, fit, expected):
    with decode_image(FIXTURES / "orientation-6.heic", budget, fit=fit) as image:
        assert image.size == expected


@pytest.mark.parametrize("orientation", range(1, 9))
@pytest.mark.parametrize("extension", ["jpg", "tiff", "tif", "heic"])
@pytest.mark.parametrize("fit", ["contain", "cover"])
def test_pixel_budget_uses_visual_dimensions_for_all_orientations(tmp_path, orientation, extension, fit):
    path = tmp_path / f"photo.{extension}"
    if extension == "heic":
        shutil.copyfile(FIXTURES / f"orientation-{orientation}.heic", path)
    else:
        exif = Image.Exif()
        exif[274] = orientation
        options = ({"quality": 100, "subsampling": 0} if extension == "jpg"
                   else {"compression": "raw" if extension == "tiff" else "tiff_lzw"})
        pattern().save(path, exif=exif.tobytes(), **options)
    if orientation in (5, 6, 7, 8):
        expected_size = (12, 18) if fit == "contain" else (24, 36)
    else:
        expected_size = (24, 16) if fit == "contain" else (27, 18)
    expected = pattern()
    if orientation != 1:
        expected = expected.transpose(TRANSFORMS[orientation])
    expected = expected.resize(expected_size, Image.Resampling.LANCZOS)
    with decode_image(path, (24, 18), fit=fit) as image:
        assert_corners(image, expected, tolerance=6)


def test_real_ten_bit_stream_decodes_to_existing_sdr_contract():
    path = FIXTURES / "ten-bit.heic"
    with open_image(path) as image:
        assert image.info["bit_depth"] == 10
    with decode_image(path) as image:
        assert image.mode == "RGB"
        assert_corners(image, pattern())


def test_heif_alpha_is_preserved_in_pillow_and_qt(app):
    path = FIXTURES / "alpha.heic"
    with decode_image(path) as image:
        assert image.mode == "RGBA"
        assert image.getchannel("A").getextrema() == (128, 128)
    image = load_qimage(path)
    assert image.hasAlphaChannel()
    assert image.pixelColor(10, 10).alpha() == 128
    assert image.colorSpace().isValid()


def test_display_p3_nclx_converts_to_srgb():
    path = FIXTURES / "display-p3.heic"
    profile = ROOT / "src/photoalbum/images/profiles/DisplayP3-v4.icc"
    with open_image(path) as source:
        assert "icc_profile" not in source.info
        assert source.info["nclx_profile"]["color_primaries"] == 12
        expected = ImageCms.profileToProfile(source, str(profile), ImageCms.createProfile("sRGB"), outputMode="RGB")
        raw_pixel = source.getpixel((24, 16))
    with decode_image(path) as image:
        assert_corners(image, expected, tolerance=0)
        assert image.getpixel((24, 16)) != raw_pixel


def test_icc_conversion_and_invalid_profile_fallback(tmp_path, caplog):
    lab = Image.new("LAB", (20, 10), (130, 150, 170))
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB"))
    path = tmp_path / "lab.tiff"
    lab.save(path, icc_profile=profile.tobytes())
    expected = ImageCms.profileToProfile(lab, profile, ImageCms.createProfile("sRGB"), outputMode="RGB")
    with decode_image(path) as image:
        assert image.mode == "RGB"
        assert image.getpixel((0, 0)) == expected.getpixel((0, 0))
    path = tmp_path / "broken-profile.png"
    pattern().save(path, icc_profile=b"invalid")
    with decode_image(path) as image:
        assert_corners(image, pattern(), tolerance=0)
    assert "ICC profile" in caplog.text


def test_corrupt_images_fail_cleanly(app, tmp_path):
    path = tmp_path / "broken.heic"
    path.write_bytes((FIXTURES / "orientation-6.heic").read_bytes()[:100])
    with pytest.raises((OSError, ValueError, SyntaxError)):
        decode_image(path)
    assert load_qimage(path).isNull()
    with pytest.raises(ValueError):
        decode_image(FIXTURES / "orientation-6.heic", (0, 10))


@pytest.mark.parametrize("path", [None, "", "missing-photo.heic"])
def test_qimage_unavailable_path_returns_null_with_warning(path, caplog, monkeypatch):
    from photoalbum.rendering import image_loader
    if path in (None, ""):
        # Missing paths are handled explicitly, before reaching Pillow.
        monkeypatch.setattr(image_loader, "decode_image", lambda *a, **kw: pytest.fail("Decoded an absent path"))
    assert load_qimage(path).isNull()
    assert "Could not decode image" in caplog.text


def test_qimage_rejects_decompression_bomb_without_disabling_limits(tmp_path, caplog, monkeypatch):
    path = tmp_path / "large.jpg"
    pattern().save(path)
    pixel_limit = 96 * 64 // 3
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", pixel_limit)
    # Actual Pillow detection, using a small file and a temporarily lower limit.
    with pytest.raises(Image.DecompressionBombError):
        ExifReader().read(path)
    with pytest.raises(Image.DecompressionBombError):
        decode_image(path)
    assert load_qimage(path).isNull()
    assert "Could not decode image" in caplog.text
    assert "decompression bomb" in caplog.text
    assert Image.MAX_IMAGE_PIXELS == pixel_limit


def test_qimage_preserves_decompression_bomb_warning(tmp_path, monkeypatch):
    path = tmp_path / "warning.jpg"
    pattern().save(path)
    pixel_limit = 96 * 64 * 2 // 3
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", pixel_limit)
    with pytest.warns(Image.DecompressionBombWarning):
        image = load_qimage(path)
    assert not image.isNull()
    assert Image.MAX_IMAGE_PIXELS == pixel_limit


def test_heic_uses_all_gui_image_caches_and_invalidation(app, tmp_path):
    path = tmp_path / "mutable.heic"
    shutil.copyfile(FIXTURES / "orientation-6.heic", path)
    cache = RenderImageCache()
    pixmap = cache.load(path, QSize(96, 96))
    assert pixmap.size() == QSize(64, 96)
    widget = PhotoPlacesWidget(translator=Translator("en"))
    try:
        thumbnail = widget._thumbnail_pixmap(path)
        assert thumbnail is not None and thumbnail.height() > thumbnail.width()
    finally:
        widget.close()
    preview = PreviewImageCache()
    preview.set_resolution(96, 96, 1)
    preview.prioritize([path])
    deadline = time.monotonic() + 5
    while preview._active:
        app.processEvents()
        assert time.monotonic() < deadline
        time.sleep(.001)
    assert preview.load(path, QSize(10, 10)).size() == QSize(64, 96)
    shutil.copyfile(FIXTURES / "no-exif.heif", path)
    cache.invalidate_changed_sources()
    preview.invalidate_changed_sources()
    assert cache.load(path, QSize(96, 96)).size() == QSize(96, 64)
    assert preview.load(path, QSize(10, 10)).isNull()


def test_local_source_scan_and_database_roundtrip(tmp_path):
    from photoalbum.app import ProjectService, ProjectScanService
    folder = tmp_path / "images"
    folder.mkdir()
    path = folder / "photo.HEIC"
    shutil.copyfile(FIXTURES / "orientation-6.heic", path)
    original = path.read_bytes()
    service = ProjectService()
    project = tmp_path / "test.photoalbum"
    try:
        service.create(project)
        source = service.add_local_source(folder)
        result = ProjectScanService().scan(project_path=project, source_directory=folder, source_id=source.id)
        assert not result.errors
        photo, = service.list_photos()
        assert displayed_photo_dimensions(photo) == (64, 96)
        assert (photo.latitude, photo.longitude) == (48.5, -2.25)
        assert photo.exif_capture_datetime == datetime(2024, 6, 15, 12, 34, 56)
        service.set_photo_caption(photo.identity, "Editorial only")
        service.materialize_originals([photo])
        assert photo.path == path
    finally:
        service.close()
    assert path.read_bytes() == original


def test_synology_jpeg_thumbnail_heic_original_and_offline_cache(app, tmp_path):
    from photoalbum.app import ProjectService
    from photoalbum.sources import ProjectSource, SourceAssetCache, SynologyCredentials, SynologyPhotosSource
    from tests.test_synology_source import FakeOpener
    thumbnail = BytesIO()
    ImageOps.exif_transpose(pattern()).resize((32, 48)).save(thumbnail, format="JPEG")
    original = (FIXTURES / "orientation-6.heic").read_bytes()
    opener = FakeOpener([
        {"success": True, "data": {"sid": "test"}},
        {"success": True, "data": {"name": "test"}},
        {"success": True, "data": {"list": [{
            "id": 42, "filename": "PHOTO.HEIC", "filesize": len(original), "time": 1718454896,
            "additional": {"resolution": {"width": 64, "height": 96}, "orientation": 6,
                           "gps": {"latitude": 48.5, "longitude": -2.25}},
        }]}},
        thumbnail.getvalue(), original, {"success": True},
    ])
    provider = SynologyPhotosSource("https://nas.example/", SynologyCredentials("test", "test"), opener=opener)
    service = ProjectService()
    try:
        service.create(tmp_path / "remote.photoalbum")
        source = ProjectSource(id="nas", kind="synology-photos", name="NAS", collection_id="7", collection_name="Album")
        result = service.change_photo_source(source, provider)
        photo, = result.photos
        assert photo.path.suffix == ".heic"  # provider bytes are identified by signature
        assert photo.path.read_bytes() == thumbnail.getvalue()
        assert not load_qimage(photo.path).isNull()
        assert displayed_photo_dimensions(photo) == (64, 96)
        service.materialize_originals([photo])
        assert photo.path.read_bytes() == original
        assert RenderImageCache().load(photo.path, QSize(100, 100)).size() == QSize(64, 96)
        cached = SourceAssetCache(service.project_path)
        # Reusing an already cached original performs no further download.
        assert cached.materialize(photo, provider, quality="original") == photo.path
        offline, = cached.renderer_photos([photo], {}, quality="original", source_kinds={"nas": "synology-photos"})
        assert offline.path.read_bytes() == original
    finally:
        service.close()
    assert not opener.payloads


def test_synology_uses_the_shared_extension_policy():
    from photoalbum.sources import SynologyCredentials, SynologyPhotosSource
    from tests.test_synology_source import FakeOpener
    rows = [{"id": i, "filename": f"photo{extension.upper()}"}
            for i, extension in enumerate(sorted(SUPPORTED_EXTENSIONS))]
    rows += [{"id": 100, "filename": "unhandled.raw"}, {"id": 101}]
    provider = SynologyPhotosSource("https://nas.example/", SynologyCredentials("test", "test"),
        opener=FakeOpener([
            {"success": True, "data": {"sid": "test"}},
            {"success": True, "data": {"name": "test"}},
            {"success": True, "data": {"list": rows}},
        ]))
    assets = provider.list_assets("7")
    assert len(assets) == len(SUPPORTED_EXTENSIONS) + 1
    assert "unhandled.raw" not in {asset.filename for asset in assets}


@pytest.mark.parametrize("template_id", ["photo-page-1", "complex-photo-1", "simplex-full-photo-cover", "year-photo-scatter"])
def test_heic_pdf_contains_oriented_pixels_for_each_pack(app, tmp_path, template_id):
    from photoalbum.album import AlbumBuilder, CoverSettings, PageInstance
    from photoalbum.export import PdfExportService
    from photoalbum.template_engine import create_template_registry, register_discovered_template_extensions
    from tests.test_album_preview_widget import make_settings
    registry = create_template_registry()
    register_discovered_template_extensions()
    photo = PhotoAnalyzer().analyze(FIXTURES / "orientation-6.heic")
    settings = make_settings()
    settings.year_dividers = replace(settings.year_dividers, enabled=False)
    settings.month_dividers = replace(settings.month_dividers, enabled=False)
    if template_id in {"simplex-full-photo-cover", "year-photo-scatter"}:
        settings.covers = {pos: CoverSettings(position=pos, template_id=template_id) for pos in settings.covers}
    else:
        settings.photo_pages = replace(settings.photo_pages, page=PageInstance(template_id))
    result = AlbumBuilder(registry).build([photo], settings)
    output = tmp_path / "heic.pdf"
    PdfExportService(Translator("en")).export(output_path=output, result=result, settings=settings,
        photos=[photo], page_width_mm=100, page_height_mm=150, dpi=72)
    reader = PdfReader(output)
    pages = reader.pages[:2] if template_id in {"simplex-full-photo-cover", "year-photo-scatter"} else reader.pages[2:-2]
    images = [image.image for page in pages for image in page.images]
    assert images, f"No HEIC pixels in {template_id} PDF"
    assert any(im.height > im.width for im in images)
    for image in images:
        if image.height > image.width:
            pixel = image.convert("RGB").getpixel((image.width // 4, image.height // 4))
            assert pixel[2] > 170 and pixel[0] < 90, pixel


def test_packaged_image_check_exercises_real_pdf(app, tmp_path):
    check = runpy.run_path(str(ROOT / "packaging/pyinstaller/image_check.py"))["check_image"]
    check(FIXTURES / "orientation-6.heic", tmp_path / "artifact-check.pdf")


def test_core_image_services_import_without_qt_sources_or_packs():
    script = '''
import importlib.abc
import sys
class BlockDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('PySide6', 'photoalbum.sources', 'photoalbum.templates')):
            raise AssertionError(fullname)
sys.meta_path.insert(0, BlockDependencies())
from photoalbum.images import decode_image, ExifReader
assert decode_image(sys.argv[1]).size == (64, 96)
assert ExifReader().read(sys.argv[1]).latitude == 48.5
'''
    subprocess.run([sys.executable, "-c", script, str(FIXTURES / "orientation-6.heic")], check=True, capture_output=True)


def test_codec_ownership_stays_in_image_layer():
    root = ROOT / "src/photoalbum"
    for path in root.rglob("*.py"):
        if "images" in path.relative_to(root).parts:
            continue
        source = path.read_text(encoding="utf-8")
        assert "pillow_heif" not in source, path
        assert "Image.open(" not in source, path
        assert "QImageReader" not in source, path
