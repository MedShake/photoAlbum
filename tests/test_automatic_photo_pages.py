from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path

import pytest

from photoalbum.album import (
    AlbumBuilder,
    AlbumStructureSettings,
    AutomaticPhotoPageModeDefinition,
    AutomaticPhotoPageSettings,
    BodyPageInsertion,
    ContentAnchor,
    CoverPosition,
    CoverSettings,
    DividerSettings,
    PageInstance,
    PageOrientation,
    PhotoPageOverride,
    PhotoPageSettings,
    TemplateDefinition,
    TemplateKind,
    TemplateRegistry,
    album_settings_from_json,
    album_settings_to_json,
)
from photoalbum.models import Photo
from photoalbum.template_engine import create_template_registry


MODE_ID = "msb-orientation-1-2"


def photo(name: str, width: int | None, height: int | None, *, orientation=None, day=1):
    return Photo(
        path=Path(f"/{name}.jpg"),
        filename=f"{name}.jpg",
        capture_datetime=datetime(2025, 3, day),
        width=width,
        height=height,
        orientation=orientation,
    )


def automatic_settings(*, landscape=True, shared=None) -> AlbumStructureSettings:
    return AlbumStructureSettings(
        covers={
            position: CoverSettings(position, template_id="year-photo-scatter")
            for position in CoverPosition
        },
        day_dividers=DividerSettings(False, "day-divider-simple"),
        month_dividers=DividerSettings(False, "month-divider-simple"),
        year_dividers=DividerSettings(False, "year-divider-classic"),
        photo_pages=PhotoPageSettings(
            automatic_mode=AutomaticPhotoPageSettings(
                MODE_ID, settings=dict(shared or {})
            )
        ),
        orientation=(
            PageOrientation.LANDSCAPE if landscape else PageOrientation.PORTRAIT
        ),
    )


def photo_pages(result):
    return [page for page in result.pagination.pages if page.photos]


def test_msb_mode_is_discovered_and_is_the_new_default():
    registry = create_template_registry()
    mode = registry.get_automatic_photo_page_mode(MODE_ID)
    assert mode.pack_id == "msb"
    assert mode.template_ids == ("photo-page-1", "photo-page-2")
    assert registry.pack_defaults["msb"]["photo_page"] == MODE_ID


def test_mode_rejects_missing_non_photo_and_cross_pack_templates():
    registry = TemplateRegistry([
        TemplateDefinition("own", "Own", frozenset({TemplateKind.PHOTO_PAGE}), 1,
                           pack_id="one"),
        TemplateDefinition("foreign", "Foreign", frozenset({TemplateKind.PHOTO_PAGE}), 1,
                           pack_id="two"),
        TemplateDefinition("cover", "Cover", frozenset({TemplateKind.COVER}), pack_id="one"),
    ])
    with pytest.raises(ValueError, match="unknown template"):
        registry.register_automatic_photo_page_mode(AutomaticPhotoPageModeDefinition(
            "bad", "Bad", "one", "One", ("missing",), "missing"
        ))
    with pytest.raises(ValueError, match="non-photo-page"):
        registry.register_automatic_photo_page_mode(AutomaticPhotoPageModeDefinition(
            "bad", "Bad", "one", "One", ("cover",), "cover"
        ))
    with pytest.raises(ValueError, match="another pack"):
        registry.register_automatic_photo_page_mode(AutomaticPhotoPageModeDefinition(
            "bad", "Bad", "one", "One", ("foreign",), "foreign"
        ))


def test_automatic_settings_roundtrip_and_schema_three_fixed_choice():
    settings = automatic_settings(shared={"photo_caption": {"show_location": False}})
    encoded = album_settings_to_json(settings)
    assert json.loads(encoded)["schema_version"] == 4
    assert album_settings_from_json(encoded) == settings

    fixed = replace(settings, photo_pages=PhotoPageSettings("photo-page-4"))
    old = json.loads(album_settings_to_json(fixed))
    old["schema_version"] = 3
    assert album_settings_from_json(json.dumps(old)).photo_pages == fixed.photo_pages


@pytest.mark.parametrize(
    ("landscape", "dimensions", "expected"),
    [
        (True, [(2, 3), (2, 3)], ["photo-page-2"]),
        (True, [(2, 3), (3, 2)], ["photo-page-1", "photo-page-1"]),
        (True, [(3, 2), (2, 3)], ["photo-page-1", "photo-page-1"]),
        (True, [(3, 2), (3, 2)], ["photo-page-1", "photo-page-1"]),
        (False, [(3, 2), (3, 2)], ["photo-page-2"]),
        (True, [(2, 2), (2, 3)], ["photo-page-1", "photo-page-1"]),
        (True, [(None, None), (2, 3)], ["photo-page-1", "photo-page-1"]),
    ],
)
def test_msb_orientation_selection(landscape, dimensions, expected):
    photos = [photo(str(index), width, height, day=index + 1)
              for index, (width, height) in enumerate(dimensions)]
    result = AlbumBuilder(create_template_registry()).build(
        photos, automatic_settings(landscape=landscape)
    )
    assert [page.template_id for page in photo_pages(result)] == expected


def test_msb_orientation_sequence_and_exif_axis_swap():
    sequence = [(2, 3), (2, 3), (3, 2), (2, 3), (2, 3), (2, 3)]
    photos = [photo(str(index), *dimensions, day=index + 1)
              for index, dimensions in enumerate(sequence)]
    pages = photo_pages(AlbumBuilder(create_template_registry()).build(
        photos, automatic_settings()
    ))
    assert [len(page.photos) for page in pages] == [2, 1, 2, 1]

    swapped = [
        photo("a", 3, 2, orientation=6, day=1),
        photo("b", 3, 2, orientation=8, day=2),
    ]
    pages = photo_pages(AlbumBuilder(create_template_registry()).build(
        swapped, automatic_settings()
    ))
    assert [page.template_id for page in pages] == ["photo-page-2"]

    square = automatic_settings()
    square.page_format = "custom"
    square.custom_width_mm = square.custom_height_mm = 200
    pages = photo_pages(AlbumBuilder(create_template_registry()).build(
        [photo("c", 2, 3, day=1), photo("d", 2, 3, day=2)], square
    ))
    assert [page.template_id for page in pages] == ["photo-page-1", "photo-page-1"]


def test_automatic_mode_respects_override_insertion_and_chronological_boundaries():
    registry = create_template_registry()
    photos = [photo("a", 2, 3, day=1), photo("b", 2, 3, day=2)]

    overridden = automatic_settings()
    overridden.photo_page_overrides = [
        PhotoPageOverride(photos[1].identity, PageInstance("photo-page-1"))
    ]
    pages = photo_pages(AlbumBuilder(registry).build(photos, overridden))
    assert [len(page.photos) for page in pages] == [1, 1]

    inserted = automatic_settings()
    inserted.body_insertions = [BodyPageInsertion(
        ContentAnchor("photo", photo_identity=photos[0].identity),
        PageInstance("dedication"),
    )]
    pages = photo_pages(AlbumBuilder(registry).build(photos, inserted))
    assert [len(page.photos) for page in pages] == [1, 1]

    separated = automatic_settings()
    separated.day_dividers = replace(separated.day_dividers, enabled=True)
    pages = photo_pages(AlbumBuilder(registry).build(photos, separated))
    assert [len(page.photos) for page in pages] == [1, 1]


def test_manual_override_is_concrete_and_shared_mode_settings_reach_both_layouts():
    registry = create_template_registry()
    registry.register(TemplateDefinition(
        "foreign-photo", "Foreign", frozenset({TemplateKind.PHOTO_PAGE}),
        photo_capacity=1, pack_id="foreign", pack_name="Foreign",
    ))
    shared = {"photo_caption": {"show_datetime": False}}
    photos = [
        photo("a", 3, 2, day=1),
        photo("b", 2, 3, day=2),
        photo("c", 2, 3, day=3),
    ]
    settings = automatic_settings(shared=shared)
    settings.photo_page_overrides = [
        PhotoPageOverride(photos[0].identity, PageInstance("foreign-photo"))
    ]
    pages = photo_pages(AlbumBuilder(registry).build(photos, settings))
    assert [page.template_id for page in pages] == ["foreign-photo", "photo-page-2"]
    assert pages[1].page_instance.settings == shared
    assert all(page.template_id != MODE_ID for page in pages)

    settings.photo_page_overrides = []
    pages = photo_pages(AlbumBuilder(registry).build(photos, settings))
    assert [page.template_id for page in pages] == ["photo-page-1", "photo-page-2"]
    assert all(page.page_instance.settings == shared for page in pages)


def test_mode_runtime_output_must_be_one_of_its_declared_templates(monkeypatch):
    from photoalbum.templates.msb.photo_page import automatic

    registry = create_template_registry()
    registry.register_automatic_photo_page_mode(AutomaticPhotoPageModeDefinition(
        "bad-runtime", "Bad runtime", "msb", "MSB",
        ("photo-page-1",), "photo-page-1",
        "photoalbum.templates.msb.photo_page.automatic:select_orientation_template",
    ))
    monkeypatch.setattr(automatic, "select_orientation_template", lambda context: "dedication")
    settings = automatic_settings()
    settings.photo_pages = PhotoPageSettings(
        automatic_mode=AutomaticPhotoPageSettings("bad-runtime")
    )
    with pytest.raises(ValueError, match="returned undeclared template"):
        AlbumBuilder(registry).build([photo("a", 2, 3)], settings)


def test_removing_manual_override_reactivates_the_automatic_mode():
    registry = create_template_registry()
    photos = [photo("a", 2, 3, day=1), photo("b", 2, 3, day=2)]
    settings = automatic_settings()
    settings.photo_page_overrides = [
        PhotoPageOverride(photos[0].identity, PageInstance("photo-page-1"))
    ]
    overridden = photo_pages(AlbumBuilder(registry).build(photos, settings))
    assert [page.template_id for page in overridden] == [
        "photo-page-1", "photo-page-1"
    ]

    settings.photo_page_overrides = []
    automatic = photo_pages(AlbumBuilder(registry).build(photos, settings))
    assert [page.template_id for page in automatic] == ["photo-page-2"]
