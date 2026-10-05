from dataclasses import replace
import json

import pytest

from photoalbum.album import (
    AlbumBuilder, AlbumSummaryBuilder, BodyPageInsertion, ContentAnchor,
    PageConstraints, PageInstance, PhotoPageOverride, PlanItemKind,
    TemplateDefinition, TemplateKind, PhotoPageSettings,
    album_settings_from_json, album_settings_to_json,
)
from photoalbum.models import PhotoUsage
from photoalbum.template_engine import create_template_registry
from tests.test_album_builder import make_registry, make_settings, make_photo


def setup_album():
    registry = make_registry()
    for capacity in (1, 3):
        registry.register(TemplateDefinition(f"photo-{capacity}", str(capacity),
            frozenset({TemplateKind.PHOTO_PAGE}), photo_capacity=capacity))
    registry.register(TemplateDefinition("inline", "Inline",
        frozenset({TemplateKind.BODY_SPECIAL_PAGE})))
    settings = make_settings()
    settings.front_matter = []
    settings.month_dividers = replace(settings.month_dividers, enabled=False)
    settings.year_dividers = replace(settings.year_dividers, enabled=False)
    photos = [make_photo(letter, 2025, 3, 1) for letter in "ABCDEFG"]
    return registry, settings, photos


def page_photos(result):
    return [[p.filename for p in page.photos] for page in result.pagination.pages if page.photos]


def test_overrides_force_start_and_only_apply_to_one_page():
    registry, settings, photos = setup_album()
    settings.photo_page_overrides = [
        PhotoPageOverride(photos[1].identity, PageInstance("photo-1")),
        PhotoPageOverride(photos[3].identity, PageInstance("photo-3")),
    ]
    result = AlbumBuilder(registry).build(photos, settings)
    assert page_photos(result) == [["A"], ["B"], ["C"], ["D", "E", "F"], ["G"]]
    assert [page.photo_capacity for page in result.pagination.pages] == [2, 1, 2, 3, 2]
    assert [page.number for page in result.pagination.pages] == [1, 2, 3, 4, 5]


def test_insertions_force_end_remain_attached_when_previous_capacity_changes():
    registry, settings, photos = setup_album()
    first, second = PageInstance("inline"), PageInstance("inline")
    anchor = ContentAnchor("photo", photo_identity=photos[3].identity)
    settings.body_insertions = [BodyPageInsertion(anchor, first), BodyPageInsertion(anchor, second)]
    for template in ("photo-1", "photo-2", "photo-3"):
        settings.photo_pages = PhotoPageSettings(template)
        result = AlbumBuilder(registry).build(photos, settings)
        pages = result.pagination.pages
        index = next(i for i, page in enumerate(pages) if page.page_instance == first)
        assert pages[index - 1].photos[-1].identity == photos[3].identity
        assert pages[index + 1].page_instance == second
        assert pages[index + 2].photos[0].identity == photos[4].identity
        assert (pages[index].year, pages[index].month, pages[index].day) == (2025, 3, 1)
        assert [page.number for page in pages] == list(range(1, len(pages) + 1))
        assert [page.side.value for page in pages] == ["right" if n % 2 else "left" for n in range(1, len(pages) + 1)]


def test_disabled_and_missing_anchors_are_dormant_without_losing_settings():
    registry, settings, photos = setup_album()
    settings.photo_page_overrides = [PhotoPageOverride(photos[1].identity, PageInstance("photo-1"))]
    settings.body_insertions = [BodyPageInsertion(ContentAnchor("photo", photo_identity=photos[1].identity), PageInstance("inline"))]
    original = album_settings_to_json(settings)
    photos[1].usage = PhotoUsage.OFF
    result = AlbumBuilder(registry).build(photos, settings)
    assert not any(page.kind == PlanItemKind.BODY_SPECIAL_PAGE for page in result.pagination.pages)
    assert original == album_settings_to_json(settings)
    photos[1].usage = PhotoUsage.BODY
    assert page_photos(AlbumBuilder(registry).build(photos, settings))[:2] == [["A"], ["B"]]
    settings.body_insertions = [replace(settings.body_insertions[0], enabled=False)]
    assert not any(page.kind == PlanItemKind.BODY_SPECIAL_PAGE for page in AlbumBuilder(registry).build(photos, settings).pagination.pages)


def test_album_pool_includes_template_only_and_excludes_off():
    registry, settings, photos = setup_album()
    photos[1].usage = PhotoUsage.TEMPLATE_ONLY
    photos[2].usage = PhotoUsage.OFF
    result = AlbumBuilder(registry).build(photos, settings)
    assert [photo.filename for photo in result.template_photos] == list("ABDEFG")
    assert [name for page in page_photos(result) for name in page] == list("ADEFG")
    assert AlbumSummaryBuilder().build(result).photo_count == 5


def test_incompatible_directives_preserve_preferences_and_body_photos():
    registry, settings, photos = setup_album()
    registry.register(TemplateDefinition("wide", "Wide", frozenset({TemplateKind.PHOTO_PAGE}),
        photo_capacity=1, page_constraints=PageConstraints(min_width_mm=400)))
    registry.register(TemplateDefinition("wide-inline", "Wide inline", frozenset({TemplateKind.BODY_SPECIAL_PAGE}),
        page_constraints=PageConstraints(min_width_mm=400)))
    override = PageInstance("wide")
    insertion = PageInstance("wide-inline")
    settings.photo_page_overrides = [PhotoPageOverride(photos[1].identity, override)]
    settings.body_insertions = [BodyPageInsertion(ContentAnchor("photo", photo_identity=photos[1].identity), insertion)]
    result = AlbumBuilder(registry).build(photos, settings)
    assert result.excluded_photo_overrides == (override,)
    assert result.excluded_special_pages == (insertion,)
    assert [name for page in page_photos(result) for name in page] == list("ABCDEFG")
    assert settings.photo_page_overrides[0].page is override


def test_semantic_divider_anchor_and_inline_do_not_split_month_diagnostics():
    registry, settings, photos = setup_album()
    settings.month_dividers = replace(settings.month_dividers, enabled=True)
    instance = PageInstance("inline")
    settings.body_insertions = [BodyPageInsertion(ContentAnchor("month_divider", year=2025, month=3), instance)]
    baseline = AlbumBuilder(registry).build(photos, replace(settings, body_insertions=[]))
    result = AlbumBuilder(registry).build(photos, settings)
    index = next(i for i, page in enumerate(result.pagination.pages) if page.page_instance == instance)
    assert result.pagination.pages[index - 1].kind == PlanItemKind.MONTH_DIVIDER
    assert result.pagination.period_end_capacities == baseline.pagination.period_end_capacities


def test_schema_three_roundtrip_and_schema_two_defaults():
    _, settings, photos = setup_album()
    settings.photo_page_overrides = [PhotoPageOverride(photos[0].identity, PageInstance("photo-1", settings={"arbitrary": 3}))]
    settings.body_insertions = [BodyPageInsertion(ContentAnchor("photo", photo_identity=photos[1].identity), PageInstance("inline"), False)]
    encoded = album_settings_to_json(settings)
    assert album_settings_from_json(encoded) == settings
    data = json.loads(encoded)
    data["schema_version"] = 2
    del data["photo_page_overrides"], data["body_insertions"]
    restored = album_settings_from_json(json.dumps(data))
    assert restored.photo_page_overrides == restored.body_insertions == []
    assert restored.photo_pages == settings.photo_pages


def test_terminal_inline_boundary_cannot_offer_spare_photo_slots():
    registry, settings, photos = setup_album()
    settings.body_insertions = [BodyPageInsertion(
        ContentAnchor("photo", photo_identity=photos[-1].identity), PageInstance("inline"))]
    result = AlbumBuilder(registry).build(photos, settings)
    assert result.pagination.pages[-2].unused_photo_slots == 1
    assert result.pagination.period_end_capacities[0].unused_photo_slots == 0


def test_only_opted_in_builtin_templates_allow_body_insertion():
    templates = create_template_registry().list_by_kind(TemplateKind.BODY_SPECIAL_PAGE)
    assert {template.template_id for template in templates} == {"dedication", "blank", "simplex-full-photo-cover"}
