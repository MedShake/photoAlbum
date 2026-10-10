import pytest
from datetime import datetime
from pathlib import Path

from photoalbum.templates.msb.year_photo_scatter.composition import (
    compose_cover_scatter,
    cover_period_title,
)
from photoalbum.models import Photo


def photo(
    name: str,
    year: int,
    month: int,
    day: int,
) -> Photo:
    return Photo(
        path=Path("/photos") / name,
        filename=name,
        capture_datetime=datetime(
            year,
            month,
            day,
        ),
        width=4000,
        height=3000,
    )


def month_name(month: int) -> str:
    return {
        3: "mars",
        4: "avril",
    }.get(month, str(month))


def test_single_month_title():
    photos = [
        photo("a.jpg", 2025, 3, 1),
        photo("b.jpg", 2025, 3, 20),
    ]

    assert (
        cover_period_title(
            photos,
            month_name,
        )
        == "Mars 2025"
    )


def test_single_year_title():
    photos = [
        photo("a.jpg", 2025, 3, 1),
        photo("b.jpg", 2025, 4, 20),
    ]

    assert (
        cover_period_title(
            photos,
            month_name,
        )
        == "2025"
    )


def test_multi_year_title():
    photos = [
        photo("a.jpg", 2024, 3, 1),
        photo("b.jpg", 2026, 4, 20),
    ]

    assert (
        cover_period_title(
            photos,
            month_name,
        )
        == "2024–2026"
    )


def test_same_seed_is_reproducible():
    photos = [
        photo(
            f"{index}.jpg",
            2025,
            3,
            index + 1,
        )
        for index in range(10)
    ]

    first = compose_cover_scatter(
        photos,
        seed=12345,
        month_name=month_name,
    )

    second = compose_cover_scatter(
        photos,
        seed=12345,
        month_name=month_name,
    )

    assert first == second


def test_different_seed_changes_proposal():
    photos = [
        photo(
            f"{index}.jpg",
            2025,
            3,
            index + 1,
        )
        for index in range(10)
    ]

    first = compose_cover_scatter(
        photos,
        seed=1,
        month_name=month_name,
    )

    second = compose_cover_scatter(
        photos,
        seed=2,
        month_name=month_name,
    )

    assert first != second


def test_classic_cover_uses_all_dated_photos():
    photos = [
        photo(
            f"{index}.jpg",
            2025,
            3,
            index + 1,
        )
        for index in range(10)
    ]

    composition = compose_cover_scatter(
        photos,
        seed=123,
        month_name=month_name,
    )

    # The classic built-in cover deliberately reproduces
    # the historical PHP behavior: every dated photo is used.
    assert len(composition.items) == 10


def test_completely_hidden_photo_is_removed():
    from photoalbum.album.composition import NormalizedRect
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        CoverScatterItem,
        visible_cover_scatter_items,
    )

    bottom = photo(
        "bottom.jpg",
        2025,
        3,
        1,
    )
    top = photo(
        "top.jpg",
        2025,
        3,
        2,
    )

    rect = NormalizedRect(
        x=0.1,
        y=0.1,
        width=0.3,
        height=0.3,
    )

    items = (
        CoverScatterItem(bottom, rect),
        CoverScatterItem(top, rect),
    )

    visible = visible_cover_scatter_items(
        items
    )

    assert visible == (
        items[1],
    )


def test_partially_visible_photo_is_kept():
    from photoalbum.album.composition import NormalizedRect
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        CoverScatterItem,
        visible_cover_scatter_items,
    )

    bottom = photo(
        "bottom.jpg",
        2025,
        3,
        1,
    )
    top = photo(
        "top.jpg",
        2025,
        3,
        2,
    )

    items = (
        CoverScatterItem(
            bottom,
            NormalizedRect(
                0.1,
                0.1,
                0.4,
                0.4,
            ),
        ),
        CoverScatterItem(
            top,
            NormalizedRect(
                0.2,
                0.2,
                0.2,
                0.2,
            ),
        ),
    )

    assert (
        visible_cover_scatter_items(
            items
        )
        == items
    )


def test_png_is_not_used_as_opaque_occluder():
    from photoalbum.album.composition import NormalizedRect
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        CoverScatterItem,
        visible_cover_scatter_items,
    )

    bottom = photo(
        "bottom.jpg",
        2025,
        3,
        1,
    )

    png = photo(
        "overlay.png",
        2025,
        3,
        2,
    )

    rect = NormalizedRect(
        0.1,
        0.1,
        0.3,
        0.3,
    )

    items = (
        CoverScatterItem(bottom, rect),
        CoverScatterItem(png, rect),
    )

    assert (
        visible_cover_scatter_items(
            items
        )
        == items
    )


def test_scatter_physical_sizes_follow_page_format():
    photos = [
        photo(
            "landscape.jpg",
            2025,
            3,
            1,
        )
    ]

    a4 = compose_cover_scatter(
        photos,
        seed=123,
        month_name=month_name,
        page_width_mm=210.0,
        page_height_mm=297.0,
    )

    letter = compose_cover_scatter(
        photos,
        seed=123,
        month_name=month_name,
        page_width_mm=215.9,
        page_height_mm=279.4,
    )

    assert len(a4.items) == 1
    assert len(letter.items) == 1

    a4_rect = a4.items[0].rect
    letter_rect = letter.items[0].rect

    # The normalized geometry changes with the paper size,
    # but the resulting physical dimensions remain constant.
    assert a4_rect.width != letter_rect.width

    assert (
        a4_rect.width * 210.0
        == pytest.approx(
            letter_rect.width * 215.9
        )
    )

    assert (
        a4_rect.height * 297.0
        == pytest.approx(
            letter_rect.height * 279.4
        )
    )


def test_frozen_scatter_keeps_geometry_after_photo_collection_changes():
    from photoalbum.album import PageInstance
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        freeze_cover_scatter, stored_cover_scatter, visible_cover_scatter_items,
    )

    original = [photo(f"freeze-{n}.jpg", 2025, 3, n + 1) for n in range(12)]
    initial = compose_cover_scatter(original, seed=91, month_name=month_name)
    snapshot = freeze_cover_scatter(initial)
    page = PageInstance(
        template_id="year-photo-scatter",
        settings={"scatter": {
            "seeds": [91], "selected_seed_index": 0, "proposals": [snapshot],
        }},
    )
    restored = stored_cover_scatter(
        page, original + [photo("extra.jpg", 2025, 4, 2)],
        month_name=month_name, page_width_mm=210, page_height_mm=297,
    )
    assert restored.title == snapshot["title"]
    assert [item.photo.identity for item in restored.items] == [
        entry["photo_id"] for entry in snapshot["items"]
    ]
    assert len(restored.items) <= len(initial.items)
    assert all(item.rect == expected.rect for item, expected in zip(
        restored.items,
        visible_cover_scatter_items(initial.items),
    ))


def test_frozen_scatter_keeps_missing_slot_instead_of_recomposing():
    from photoalbum.album import PageInstance
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        freeze_cover_scatter, stored_cover_scatter, visible_cover_scatter_items,
    )
    original = [photo(f"lost-{n}.jpg", 2025, 3, n + 1) for n in range(12)]
    snapshot = freeze_cover_scatter(compose_cover_scatter(
        original, seed=25, month_name=month_name,
    ))
    assert snapshot["items"]
    missing_id = snapshot["items"][0]["photo_id"]
    page = PageInstance(template_id="year-photo-scatter", settings={
        "scatter": {"seeds": [25], "proposals": [snapshot]}
    })
    restored = stored_cover_scatter(
        page, [p for p in original if p.identity != missing_id],
        month_name=month_name, page_width_mm=210, page_height_mm=297,
    )
    assert restored.items[0].photo is None
    assert len(restored.items) == len(snapshot["items"])


def test_frozen_proposal_is_bound_to_original_page_dimensions():
    from photoalbum.album import PageInstance
    from photoalbum.templates.msb.year_photo_scatter.composition import (
        freeze_cover_scatter, proposal_matches_dimensions, stored_cover_scatter,
    )

    photos = [photo(f"image-{i}.jpg", 2025, 3, i + 1) for i in range(6)]
    old_composition = compose_cover_scatter(
        photos, seed=33, month_name=month_name,
        page_width_mm=210.0, page_height_mm=297.0,
    )
    frozen = freeze_cover_scatter(
        old_composition, page_width_mm=210.0, page_height_mm=297.0,
    )
    assert proposal_matches_dimensions(frozen, 210.0, 297.0)
    assert not proposal_matches_dimensions(frozen, 297.0, 210.0)

    instance = PageInstance("year-photo-scatter", settings={"scatter": {
        "seeds": [33], "selected_seed_index": 0, "proposals": [frozen],
    }})
    unchanged = stored_cover_scatter(
        instance, photos, month_name=month_name,
        page_width_mm=210.0, page_height_mm=297.0,
    )
    assert [
        (item.rect.x, item.rect.y, item.rect.width, item.rect.height)
        for item in unchanged.items
    ] == [tuple(record["rect"]) for record in frozen["items"]]
    resized = stored_cover_scatter(
        instance, photos, month_name=month_name,
        page_width_mm=297.0, page_height_mm=210.0,
    )
    assert resized == compose_cover_scatter(
        photos, seed=33, month_name=month_name,
        page_width_mm=297.0, page_height_mm=210.0,
    )


def test_scatter_format_change_recreates_proposal_history(monkeypatch):
    from photoalbum.album import PageInstance
    from photoalbum.templates.msb.year_photo_scatter import composition as scatter

    photos = [photo(f"image-{i}.jpg", 2025, 3, i + 1) for i in range(6)]
    first = scatter.freeze_cover_scatter(
        scatter.compose_cover_scatter(
            photos, seed=123, month_name=month_name,
            page_width_mm=210, page_height_mm=297,
        ), page_width_mm=210, page_height_mm=297,
    )
    instance = PageInstance("year-photo-scatter", settings={"scatter": {
        "seeds": [123, 456], "selected_seed_index": 1,
        "proposals": [first, first], "title_color": "#123456",
    }})
    monkeypatch.setattr(scatter, "randbelow", lambda limit: 789)
    updated = scatter.reset_frozen_scatter_for_dimensions(
        instance, photos, month_name=month_name,
        page_width_mm=297, page_height_mm=210,
    )
    new = updated.settings["scatter"]
    assert new["seeds"] == [789]
    assert new["selected_seed_index"] == 0
    assert len(new["proposals"]) == 1
    assert new["proposals"][0]["page_dimensions_mm"] == [297.0, 210.0]
    assert new["title_color"] == "#123456"
    assert scatter.reset_frozen_scatter_for_dimensions(
        updated, photos, month_name=month_name,
        page_width_mm=297, page_height_mm=210,
    ) is updated
    assert instance.settings["scatter"]["seeds"] == [123, 456]


def test_scatter_histories_restore_each_visited_page_format(monkeypatch):
    """No pre-generation, and switching back restores every slot and selection."""
    import json
    from photoalbum.album import PageInstance
    from photoalbum.templates.msb.year_photo_scatter import composition as scatter

    photos = [photo(f"picture-{i}.jpg", 2025, 3, i + 1) for i in range(7)]
    original = [scatter.freeze_cover_scatter(
        scatter.compose_cover_scatter(
            photos, seed=seed, month_name=month_name,
            page_width_mm=210, page_height_mm=297,
        ), page_width_mm=210, page_height_mm=297,
    ) for seed in (10, 11, 12)]
    instance = PageInstance("year-photo-scatter", settings={"scatter": {
        "seeds": [10, 11, 12], "proposals": original,
        "selected_seed_index": 1,
    }})
    generated_seeds = iter([99, 100])
    monkeypatch.setattr(scatter, "randbelow", lambda limit: next(generated_seeds))

    def switch(page, width, height):
        return scatter.reset_frozen_scatter_for_dimensions(
            page, photos, month_name=month_name,
            page_width_mm=width, page_height_mm=height,
        )

    landscape = switch(instance, 297, 210)
    state = landscape.settings["scatter"]
    assert state["seeds"] == [99]
    assert len(state["format_histories"]) == 2
    assert state["selected_seed_index"] == 0

    restored = switch(landscape, 210, 297)
    assert restored.settings["scatter"]["seeds"] == [10, 11, 12]
    assert restored.settings["scatter"]["proposals"] == original
    assert restored.settings["scatter"]["selected_seed_index"] == 1
    # JSON roundtrip as in project persistence.
    reloaded = PageInstance("year-photo-scatter", settings=json.loads(
        json.dumps(restored.settings)
    ))
    again = switch(reloaded, 297, 210)
    assert again.settings["scatter"]["seeds"] == [99]
    assert again.settings["scatter"]["selected_seed_index"] == 0
    assert len(again.settings["scatter"]["format_histories"]) == 2

    third = switch(again, 148, 210)
    assert third.settings["scatter"]["seeds"] == [100]
    assert len(third.settings["scatter"]["format_histories"]) == 3


def test_scatter_histories_are_per_page_not_shared(monkeypatch):
    from photoalbum.album import PageInstance
    from photoalbum.templates.msb.year_photo_scatter import composition as scatter

    photos = [photo(f"photo-{i}.jpg", 2025, 3, i + 1) for i in range(5)]
    def first(seed):
        return scatter.freeze_cover_scatter(
            scatter.compose_cover_scatter(
                photos, seed=seed, month_name=month_name,
                page_width_mm=210, page_height_mm=297,
            ), page_width_mm=210, page_height_mm=297,
        )
    a = PageInstance("year-photo-scatter", settings={"scatter": {
        "seeds": [22], "proposals": [first(22)], "selected_seed_index": 0,
    }})
    b = PageInstance("year-photo-scatter", settings={"scatter": {
        "seeds": [33], "proposals": [first(33)], "selected_seed_index": 0,
    }})
    generated = iter([44, 55])
    monkeypatch.setattr(scatter, "randbelow", lambda limit: next(generated))
    def switch(page, width, height):
        return scatter.reset_frozen_scatter_for_dimensions(
            page, photos, month_name=month_name,
            page_width_mm=width, page_height_mm=height,
        )
    a_landscape = switch(a, 297, 210)
    b_landscape = switch(b, 297, 210)
    assert a_landscape.settings["scatter"]["seeds"] == [44]
    assert b_landscape.settings["scatter"]["seeds"] == [55]
    assert switch(a_landscape, 210, 297).settings["scatter"]["seeds"] == [22]
    assert switch(b_landscape, 210, 297).settings["scatter"]["seeds"] == [33]
