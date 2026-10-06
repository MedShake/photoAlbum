"""Cross-screen contracts for source identity, usage and content directives."""
from dataclasses import replace
from datetime import datetime
from unittest.mock import Mock

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QComboBox, QPushButton, QToolButton

from photoalbum.album import (
    A4, AlbumBuilder, BodyPageInsertion, ContentAnchor, CoverSettings,
    PageInstance, PhotoPageOverride, PlanItemKind,
)
from photoalbum.app import ProjectService
from photoalbum.database import PhotoRepository
from photoalbum.export import PdfExportService
from photoalbum.gui.widgets import AlbumPreviewWidget
from photoalbum.gui.widgets.album_plan_widget import AlbumPlanWidget
from photoalbum.gui.widgets.photo_sources_widget import PhotoSourcesWidget
from photoalbum.gui.widgets.photo_places_widget import PhotoPlacesWidget
from photoalbum.i18n import Translator
from photoalbum.models import Photo, PhotoUsage
from photoalbum.sources import ProjectSource, PhotoMetadataPolicy
from photoalbum.template_engine import (
    create_template_registry, register_discovered_template_extensions,
    PageTemplateExtension, template_extension_registry,
)
from tests.test_album_preview_widget import make_settings
from tests.test_photo_places_location_sources import _photo


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def example_album(tmp_path):
    path = tmp_path / "same.jpg"
    Image.new("RGB", (60, 40), "steelblue").save(path)
    photos = [Photo(path, "same.jpg", source_id=f"source-{n}", asset_id="asset",
                    capture_datetime=datetime(2025, 3, 1), usage=usage)
              for n, usage in enumerate(PhotoUsage)]
    settings = make_settings()
    settings.month_dividers = replace(settings.month_dividers, enabled=False)
    settings.year_dividers = replace(settings.year_dividers, enabled=False)
    settings.covers = {position: CoverSettings(position=position,
        template_id="simplex-full-photo-cover") for position in settings.covers}
    settings.body_insertions = [BodyPageInsertion(
        ContentAnchor("photo", photo_identity=photos[0].identity),
        PageInstance("simplex-full-photo-cover"),
    )]
    return photos, settings


def test_selection_and_places_editors_use_identity_with_identical_paths(app, tmp_path):
    view = PhotoSourcesWidget(Translator("en"))
    first = replace(_photo(), source_id="first", asset_id="same")
    second = replace(first, source_id="second")
    view.model.set_photos([first, second])
    view.select_photo(second)
    assert view.table.currentIndex().data(Qt.ItemDataRole.UserRole).identity == second.identity
    places = PhotoPlacesWidget(translator=Translator("en"))
    places.set_source_labels({"first": "Synology Photos", "second": "Immich"})
    places.set_photos([first, second])
    year = places._tree.topLevelItem(0)
    year.setExpanded(True)
    year.child(0).setExpanded(True)
    app.processEvents()
    assert set(places._caption_editors) == {first.identity, second.identity}
    assert places._location_mode_boxes[first.identity].itemText(0) == "Synology Photos"
    assert places._location_mode_boxes[second.identity].itemText(0) == "Immich"
    assert places._caption_editors[first.identity] is not places._caption_editors[second.identity]
    places.close()
    view.close()


def test_simplex_photo_selector_prefers_identity_over_legacy_path(app, tmp_path):
    from photoalbum.templates.simplex.full_photo_cover.settings import SimplexFullPhotoCoverSettingsWidget
    from photoalbum.templates.simplex.full_photo_cover.widget_renderer import PHOTO_ASSET_KEY, PHOTO_PATH_KEY
    photos, _ = example_album(tmp_path)
    instance = PageInstance("simplex-full-photo-cover", settings={
        PHOTO_ASSET_KEY: photos[0].identity, PHOTO_PATH_KEY: str(photos[0].path),
    })
    widget = SimplexFullPhotoCoverSettingsWidget(instance, photos,
        translator=Translator("en"), page_format=A4)
    assert widget._photo_combo.currentData() == photos[0].identity
    widget._photo_combo.setCurrentIndex(1)
    assert widget._instance.settings[PHOTO_ASSET_KEY] == photos[1].identity
    widget.close()


def test_preview_pdf_and_original_preparation_share_canonical_pool(app, tmp_path, monkeypatch):
    from pypdf import PdfReader
    from photoalbum.gui.workers.pdf_export_worker import PdfExportWorker
    photos, settings = example_album(tmp_path)
    registry = create_template_registry()
    register_discovered_template_extensions()
    result = AlbumBuilder(registry).build(photos, settings)
    calls = []
    class Probe:
        def paint(self, **context):
            # Do not retain a live Qt painter after its paint device returns.
            calls.append({key: context[key] for key in ("photos", "instance", "composition")})
    monkeypatch.setattr(template_extension_registry, "_extensions", dict(template_extension_registry._extensions))
    template_extension_registry.register(PageTemplateExtension(
        "simplex-full-photo-cover", widget_renderer=Probe(), photo_scope="album"))
    preview = AlbumPreviewWidget(registry)
    preview.resize(1000, 800)
    preview.set_result(result, settings)
    preview.show()
    app.processEvents()
    preview.grab()
    assert calls
    expected = [photo.identity for photo in photos[:2]]
    assert all([photo.identity for photo in call["photos"]] == expected for call in calls)
    calls.clear()
    exporter = PdfExportService(Translator("en"))
    prepared = Mock()
    worker = PdfExportWorker(exporter, output_path=tmp_path / "album.pdf",
        result=result, settings=settings, photos=photos, page_width_mm=210,
        page_height_mm=297, dpi=36, metadata=None, content="complete", prepare_assets=prepared)
    errors = []
    worker.failed.connect(errors.append)
    worker.run()
    assert errors == []
    prepared.assert_called_once_with(list(result.template_photos))
    assert len(PdfReader(tmp_path / "album.pdf").pages) == result.total_page_count
    assert len(calls) == 5  # four covers and the inline page
    assert all([photo.identity for photo in call["photos"]] == expected for call in calls)
    inline = calls[2] if calls[2]["instance"] == settings.body_insertions[0].page else next(
        call for call in calls if call["instance"] == settings.body_insertions[0].page)
    assert inline["composition"].page.kind == PlanItemKind.BODY_SPECIAL_PAGE
    assert inline["composition"].page.day == 1
    preview.close()


def test_disabled_inline_is_visible_without_number_and_can_be_enabled_deleted(app, tmp_path):
    photos, settings = example_album(tmp_path)
    settings.body_insertions = [replace(settings.body_insertions[0], enabled=False)]
    registry = create_template_registry()
    widget = AlbumPlanWidget(registry, Translator("en"))
    widget.set_result(AlbumBuilder(registry).build(photos, settings), settings)
    row = widget._tree.topLevelItem(widget._tree.topLevelItemCount() - 1)
    assert row.text(1) == "—" and row.text(5) == "Disabled"
    buttons = widget._tree.itemWidget(row, 3).findChildren(QToolButton)
    received = []
    widget.settings_changed.connect(received.append)
    next(button for button in buttons if button.toolTip() == "Enable").click()
    assert received[-1].body_insertions[0].enabled
    assert received[-1].body_insertions[0].page.instance_id == settings.body_insertions[0].page.instance_id
    next(button for button in buttons if button.toolTip() == "Delete").click()
    assert received[-1].body_insertions == []
    widget.close()


def test_new_override_inside_exception_creates_distinct_occurrence(app, tmp_path, monkeypatch):
    from photoalbum.gui.plan_page_editor import choose_page
    from photoalbum.gui.page_instance_dialog import PageInstanceDialog
    from tests.test_body_directives import setup_album
    registry, settings, photos = setup_album()
    existing = PageInstance("photo-3")
    settings.photo_page_overrides = [PhotoPageOverride(photos[0].identity, existing)]
    result = AlbumBuilder(registry).build(photos, settings)
    def accept(dialog):
        dialog.findChildren(QComboBox)[0].setCurrentIndex(1)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, "exec", accept)
    monkeypatch.setattr(PageInstanceDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    identity, instance, _ = choose_page(None, registry, settings, result, Translator("en"),
        page=result.pagination.pages[0], instance=existing, photo_override=True)
    assert identity == photos[1].identity
    assert instance.template_id == existing.template_id
    assert instance.instance_id != existing.instance_id


def test_global_refresh_continues_after_disconnected_source(app, tmp_path):
    from photoalbum.gui.workers.sources_refresh_worker import SourcesRefreshWorker
    service = ProjectService()
    service.create(tmp_path / "album.sqlite")
    disconnected = ProjectSource(id="offline", kind="fake", name="Offline",
        collection_id="album", collection_name="Offline")
    service.set_photo_source(disconnected)
    folder = tmp_path / "photos"
    folder.mkdir()
    Image.new("RGB", (20, 20)).save(folder / "2025-01-01.jpg")
    local = service.add_local_source(folder)
    service.set_photo_metadata_policy(PhotoMetadataPolicy("exif", "exif", "none", False), local.id)
    worker = SourcesRefreshWorker(project_path=service.project_path,
        sources=service.list_sources(), providers={}, synchronize=True, language="en", user_agent="test")
    completed, logs = [], []
    worker.completed.connect(completed.append)
    worker.log_message.connect(logs.append)
    worker.run()
    assert len(completed) == 1
    assert [photo.source_id for photo in completed[0]] == [local.id]
    assert any("Offline" in message for message in logs)
    assert service.list_photos()[0].source_id == local.id
    service.close()


@pytest.mark.parametrize("placement", ["right_page", "right_page_with_blank_facing"])
def test_inline_and_overrides_keep_right_dividers_and_editorial_blanks(app, placement):
    from photoalbum.album import DividerPlacement, BlankPageReason, PageSide
    from tests.test_album_builder import make_photo
    settings = make_settings()
    settings.month_dividers = replace(settings.month_dividers, enabled=False)
    settings.year_dividers = replace(settings.year_dividers, enabled=False)
    settings.day_dividers = replace(settings.day_dividers, enabled=True, placement=DividerPlacement(placement))
    photos = [make_photo(str(n), 2025, 3, 1 if n < 3 else 2) for n in range(6)]
    settings.photo_page_overrides = [PhotoPageOverride(photos[1].identity, PageInstance("photo-page-2"))]
    settings.body_insertions = [BodyPageInsertion(ContentAnchor("photo", photo_identity=photos[2].identity), PageInstance("blank"))]
    result = AlbumBuilder(create_template_registry()).build(photos, settings)
    pages = result.pagination.pages
    dividers = [page for page in pages if page.kind == PlanItemKind.DAY_DIVIDER]
    assert len(dividers) == 2 and all(page.side == PageSide.RIGHT for page in dividers)
    if placement == "right_page_with_blank_facing":
        assert pages[dividers[1].number - 2].blank_reason == BlankPageReason.EDITORIAL
    assert [photo.identity for page in pages for photo in page.photos] == [photo.identity for photo in photos]
    inline = next(page for page in pages if page.kind == PlanItemKind.BODY_SPECIAL_PAGE)
    assert pages[inline.number - 2].photos[-1].identity == photos[2].identity
    capacities = result.pagination.period_end_capacities
    assert [
        (capacity.scope, capacity.year, capacity.month, capacity.day,
         capacity.unused_photo_slots)
        for capacity in capacities
    ] == [
        ("day", 2025, 3, 1, 0),
        ("day", 2025, 3, 2, 0),
    ]


def test_facing_override_and_default_share_caption_reserve(app):
    from photoalbum.album import PhotoPageSettings
    from photoalbum.album.composition import PageComposer
    from tests.test_album_builder import make_photo
    settings = make_settings()
    settings.month_dividers = replace(settings.month_dividers, enabled=False)
    settings.year_dividers = replace(settings.year_dividers, enabled=False)
    settings.photo_pages = PhotoPageSettings(page=PageInstance("photo-page-2", settings={
        "photo_caption": {"show_datetime": True, "show_location": True},
    }))
    photos = [make_photo(str(n), 2025, 3, 1) for n in range(5)]
    photos[2].caption = "A caption on the exceptional page"
    settings.photo_page_overrides = [PhotoPageOverride(photos[2].identity, PageInstance("photo-page-1", settings={
        "photo_caption": {"show_datetime": True, "show_location": True},
    }))]
    result = AlbumBuilder(create_template_registry()).build(photos, settings)
    left, right = result.pagination.pages[1:3]
    assert (left.photo_capacity, right.photo_capacity) == (1, 2)
    composer = PageComposer()
    left_reserve = composer.spread_caption_lines(left, result.pagination.pages, settings.photo_pages)
    right_reserve = composer.spread_caption_lines(right, result.pagination.pages, settings.photo_pages)
    assert left_reserve == right_reserve and left_reserve > 0
    for page, reserve in ((left, left_reserve), (right, right_reserve)):
        composition = composer.compose(page, settings.photo_pages, reserved_caption_lines=reserve)
        assert len(composition.photo_slots) == page.photo_capacity


def test_cli_scan_registers_source_and_reuses_it_on_refresh(tmp_path):
    from photoalbum.cli import build_parser, run_scan
    folder = tmp_path / "photos"
    folder.mkdir()
    Image.new("RGB", (20, 20)).save(folder / "2025-01-01.jpg")
    project = tmp_path / "cli.photoalbum"
    args = build_parser().parse_args(["scan", str(folder), "--project", str(project)])
    assert run_scan(args) == 0
    service = ProjectService()
    service.open(project)
    first = service.list_sources()[0]
    photo = service.list_photos()[0]
    service.set_photo_usage(photo.identity, PhotoUsage.TEMPLATE_ONLY)
    service.close()
    assert run_scan(args) == 0
    service.open(project)
    assert service.list_sources() == [first]
    assert service.list_album_photos()[0].usage == PhotoUsage.TEMPLATE_ONLY
    service.close()
