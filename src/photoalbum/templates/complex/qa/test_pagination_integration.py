"""Real host pagination with the independently discovered Complex selector."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from photoalbum.album import (
    AlbumPlan, AlbumStructureSettings, AutomaticPhotoPageSettings, DividerSettings,
    PageInstance, PageOrientation, PaginationEngine, PhotoPageOverride,
    PhotoPageSettings, PlanItem, PlanItemKind, TemplateRegistry,
)
from photoalbum.template_engine.discovery import load_template_pack
from photoalbum.models import Photo


@pytest.fixture
def pagination():
    root = Path(__file__).resolve().parents[1]
    pack = load_template_pack(root / "manifest.json")
    registry = TemplateRegistry(list(pack.templates))
    for mode in pack.automatic_photo_page_modes:
        registry.register_automatic_photo_page_mode(mode)
    mode = AutomaticPhotoPageSettings("complex-auto-1-5")
    settings = AlbumStructureSettings(
        covers={}, day_dividers=DividerSettings(False, "day"),
        month_dividers=DividerSettings(False, "month"),
        year_dividers=DividerSettings(False, "year"),
        photo_pages=PhotoPageSettings(automatic_mode=mode),
    )
    photos = tuple(
        Photo(path=Path(f"/tmp/sample{i:02}.jpg"), filename=f"sample{i:02}.jpg",
              width=4000, height=3000,
              capture_datetime=datetime(2025, 1, 1) + timedelta(minutes=i))
        for i in range(20)
    )
    plan = AlbumPlan([PlanItem(
        kind=PlanItemKind.PHOTO_GROUP, template_id=None, photos=photos,
        automatic_photo_page_mode=mode,
    )])
    return PaginationEngine(registry), plan, settings, photos


def variants(result, photos):
    pages = [page for page in result.pages if page.photos]
    assert tuple(photo for page in pages for photo in page.photos) == photos
    assert all(page.template_id == "complex-photo-5" for page in pages)
    return [page.page_instance.settings.get("layout_variant") for page in pages]


def test_regeneration_resets_rotation(pagination):
    engine, plan, settings, photos = pagination
    expected = ["five-sequence-top", "five-sequence-center", "five-sequence-bottom", "five-sequence-top"]
    assert variants(engine.paginate(plan, settings), photos) == expected
    assert variants(engine.paginate(plan, settings), photos) == expected
    assert engine._automatic_variant_counts == {("portrait", "LLLLL"): 4}


@pytest.mark.parametrize("index,manual_variant,expected", [
    (5, "five-sequence-bottom", ["five-sequence-top", "five-sequence-bottom", "five-sequence-center", "five-sequence-bottom"]),
    (0, "five-sequence-center", ["five-sequence-center", "five-sequence-top", "five-sequence-center", "five-sequence-bottom"]),
])
def test_manual_page_does_not_advance_rotation(pagination, index, manual_variant, expected):
    engine, plan, settings, photos = pagination
    settings.photo_page_overrides = [PhotoPageOverride(
        photos[index].identity,
        PageInstance("complex-photo-5", settings={"layout_variant": manual_variant}),
    )]
    assert variants(engine.paginate(plan, settings), photos) == expected
    assert engine._automatic_variant_counts == {("portrait", "LLLLL"): 3}


def test_changing_page_format_resets_rotation(pagination):
    engine, plan, settings, photos = pagination
    engine.paginate(plan, settings)
    settings.orientation = PageOrientation.LANDSCAPE
    assert variants(engine.paginate(plan, settings), photos) == [
        "five-sequence-top", "five-sequence-bottom", "five-sequence-top", "five-sequence-bottom"
    ]
    assert engine._automatic_variant_counts == {("landscape", "LLLLL"): 4}
