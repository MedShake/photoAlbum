from dataclasses import replace

import pytest
from PIL import Image
from pypdf import PdfReader
from PySide6.QtWidgets import QApplication

from photoalbum.album import AlbumBuilder, PageInstance, PhotoPageSettings
from photoalbum.export.pdf_export_service import PdfExportContent, PdfExportService
from photoalbum.gui.widgets import AlbumPlanWidget, AlbumPreviewWidget
from photoalbum.gui.widgets.album_preview_widget import AlbumPagePreview
from photoalbum.i18n import Translator
from photoalbum.template_engine import create_template_registry, register_discovered_template_extensions
from photoalbum.template_engine import discovery, translations, template_extension_registry
from tests.test_album_builder import make_photo
from tests.test_album_plan_widget import page_numbers_in_visual_order
from tests.test_album_preview_widget import make_settings


@pytest.mark.parametrize("photo_count,back_count", [(1, 0), (3, 0), (1, 1), (3, 1)])
def test_final_verso_in_plan_preview_and_pdf(tmp_path, monkeypatch, photo_count, back_count):
    app = QApplication.instance() or QApplication([])
    # Registration replaces global state; restore it after each integration case.
    monkeypatch.setattr(template_extension_registry, "_extensions", dict(template_extension_registry._extensions))
    monkeypatch.setattr(discovery, "_active_packs", dict(discovery._active_packs))
    monkeypatch.setattr(translations, "_PACK_CATALOGS", dict(translations._PACK_CATALOGS))
    monkeypatch.setattr(translations, "_TEMPLATE_PACKS", dict(translations._TEMPLATE_PACKS))
    register_discovered_template_extensions()
    registry = create_template_registry()
    settings = make_settings()
    settings.day_dividers = replace(settings.day_dividers, enabled=False)
    settings.month_dividers = replace(settings.month_dividers, enabled=False)
    settings.year_dividers = replace(settings.year_dividers, enabled=False)
    settings.photo_pages = PhotoPageSettings("photo-page-2")
    settings.back_matter = [PageInstance("blank") for _ in range(back_count)]
    photos = [make_photo(f"{i}.jpg", 2025, 3, 1) for i in range(photo_count)]
    for photo in photos:
        photo.path = tmp_path / photo.filename
        Image.new("RGB", (20, 20), "red").save(photo.path)
    builder = AlbumBuilder(registry)
    result = builder.build(photos, settings)
    pages = result.pagination.pages
    content_count = (photo_count + 1) // 2 + back_count
    expected_count = content_count + content_count % 2
    assert result.interior_page_count == expected_count
    assert result.total_page_count == expected_count + 4
    assert pages[-1].is_blank == bool(content_count % 2)

    plan = AlbumPlanWidget(registry, translator=Translator("en"))
    preview = AlbumPreviewWidget(registry)
    try:
        plan.set_result(result, settings)
        numbers = []
        for i in range(plan._tree.topLevelItemCount()):
            numbers.extend(page_numbers_in_visual_order(plan._tree.topLevelItem(i)))
        assert numbers == list(range(1, expected_count + 1))

        preview.set_result(result, settings)
        assert [w._composition.page for w in preview._page_widgets if isinstance(w, AlbumPagePreview)] == pages
        assert preview._pages_grid.itemAtPosition(1 + expected_count // 2, 0).widget()._composition.page == pages[-1]
        assert len(preview._page_widgets) == expected_count + 4

        for content, count in [(PdfExportContent.BODY, expected_count),
                               (PdfExportContent.COMPLETE, expected_count + 4),
                               (PdfExportContent.COVERS, 4)]:
            output = tmp_path / f"{content.value}.pdf"
            PdfExportService(Translator("en")).export(
                output_path=output, result=result, settings=settings, photos=photos,
                page_width_mm=210, page_height_mm=297, dpi=72, content=content,
            )
            reader = PdfReader(output)
            assert len(reader.pages) == count
            if content == PdfExportContent.BODY and pages[-1].is_blank:
                assert not list(reader.pages[-1].images)
                assert reader.pages[-1].extract_text().strip() == str(expected_count)

        if not back_count:
            spare = result.pagination.period_end_capacities[-1].unused_photo_slots
            additional = [make_photo(f"extra-{i}.jpg", 2025, 3, 2) for i in range(spare)]
            filled = builder.build(photos + additional, settings)
            assert filled.interior_page_count == expected_count
            assert filled.pagination.period_end_capacities[-1].unused_photo_slots == 0
    finally:
        plan.close()
        preview.close()
