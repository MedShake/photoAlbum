from dataclasses import asdict
from itertools import product
import json

import pytest

from photoalbum.album import (
    CoverPosition, PageConstraints, TemplateDefinition, TemplateKind, TemplateRegistry,
)
from photoalbum.template_engine import create_template_registry, discover_templates


@pytest.mark.parametrize("present", list(product((False, True), repeat=4)))
def test_optional_bounds_independently_and_in_combination(present):
    bounds = dict(zip(
        ("min_width_mm", "max_width_mm", "min_height_mm", "max_height_mm"),
        (180, 320, 150, 350),
    ))
    constraints = PageConstraints(**{
        name: value for (name, value), enabled in zip(bounds.items(), present) if enabled
    })
    template = TemplateDefinition("bounded", "Bounded", frozenset({TemplateKind.SPECIAL_PAGE}),
                                  page_constraints=constraints)
    assert template.is_compatible_with_page(210, 297)
    assert template.is_compatible_with_page(297, 210)
    assert template.is_compatible_with_page(180, 150)
    assert template.is_compatible_with_page(320, 350)
    assert template.is_compatible_with_page(179, 200) is (not present[0])
    assert template.is_compatible_with_page(321, 200) is (not present[1])
    assert template.is_compatible_with_page(200, 149) is (not present[2])
    assert template.is_compatible_with_page(200, 351) is (not present[3])
    for value, enabled in zip(asdict(constraints).values(), present):
        assert (value is not None) == enabled


@pytest.mark.parametrize("bounds", [
    {"min_width_mm": -1}, {"max_height_mm": 0}, {"min_width_mm": True},
    {"min_height_mm": "180"}, {"max_width_mm": float("inf")},
    {"max_height_mm": float("nan")},
    {"min_width_mm": 200, "max_width_mm": 100},
    {"min_height_mm": 200, "max_height_mm": 100},
])
def test_invalid_bounds_rejected(bounds):
    with pytest.raises(ValueError):
        PageConstraints(**bounds)


def test_exact_fixed_size_and_explicit_absent_bounds():
    constraints = PageConstraints(min_width_mm=123, max_width_mm=123, min_height_mm=None)
    assert constraints.accepts(123, 456)
    assert not constraints.accepts(122.9, 456)
    assert not constraints.accepts(123.1, 456)


@pytest.mark.parametrize("geometry", [(0, 10), (-1, 10), (10, float("nan")), (float("inf"), 10)])
def test_invalid_page_dimensions_rejected(geometry):
    assert not PageConstraints().accepts(*geometry)


def test_registry_filters_geometry_without_losing_kind_or_cover_positions():
    photo = TemplateDefinition("photo", "Photo", frozenset({TemplateKind.PHOTO_PAGE}),
                               photo_capacity=1, page_constraints=PageConstraints(min_width_mm=180))
    cover = TemplateDefinition("cover", "Cover", frozenset({TemplateKind.COVER}),
                               page_constraints=PageConstraints(max_height_mm=320))
    registry = TemplateRegistry([photo, cover])
    assert registry.list_for_page(TemplateKind.PHOTO_PAGE, 200, 300) == [photo]
    assert registry.list_for_page(TemplateKind.PHOTO_PAGE, 170, 300) == []
    assert registry.album_page_available(200, 300)
    assert not registry.album_page_available(170, 300)
    assert not registry.album_page_available(200, 330)
    restricted = TemplateDefinition("front", "Front", frozenset({TemplateKind.COVER}),
                                    cover_positions=frozenset({CoverPosition.FRONT}))
    assert not TemplateRegistry([photo, restricted]).album_page_available(200, 300)


def test_discovery_loads_real_constraints_from_a_new_pack(tmp_path):
    pack = tmp_path / "synthetic"
    pack.mkdir()
    manifest = pack / "manifest.json"
    data = {"schema_version": 1, "id": "synthetic", "name": "Synthetic", "templates": [{
        "id": "bounded", "name": "Bounded", "module": "unimported",
        "kinds": ["special_page"],
        "page_constraints": {"min_width_mm": 180, "max_height_mm": 320},
    }]}
    manifest.write_text(json.dumps(data))
    template = discover_templates(tmp_path).registry.get("bounded")
    assert template.is_compatible_with_page(180, 320)
    assert not template.is_compatible_with_page(179, 320)
    assert not template.is_compatible_with_page(180, 321)
    assert template.is_compatible_with_page(1000, 10)
    for invalid in ({"ratio": 2}, {"min_width_mm": "180"}, [], None):
        data["templates"][0]["page_constraints"] = invalid
        manifest.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            discover_templates(tmp_path)


def test_production_templates_only_have_documented_geometric_restrictions():
    registry = create_template_registry()
    assert registry.list_all()
    for template in registry.list_all():
        documented = {
            "month-divider-classic": PageConstraints(min_width_mm=130, min_height_mm=145),
            "calendar-index": PageConstraints(min_width_mm=180, min_height_mm=180),
        }
        assert template.page_constraints == documented.get(template.template_id, PageConstraints())
        for width, height in [(210, 297), (297, 210), (148, 210), (279.4, 215.9), (123, 456), (456, 123)]:
            if template.template_id not in documented:
                assert template.is_compatible_with_page(width, height)
        if template.template_id in documented:
            bounds = template.page_constraints
            assert template.is_compatible_with_page(bounds.min_width_mm, bounds.min_height_mm)
            assert not template.is_compatible_with_page(bounds.min_width_mm - 1, bounds.min_height_mm)
            assert not template.is_compatible_with_page(bounds.min_width_mm, bounds.min_height_mm - 1)


def test_classic_month_minimum_keeps_city_rectangle_and_bottom_margin_on_page():
    from photoalbum.templates.msb.month_divider_classic.layout import classic_month_divider_layout

    template = create_template_registry().get("month-divider-classic")
    bounds = template.page_constraints
    layout = classic_month_divider_layout(
        page_width_mm=bounds.min_width_mm, page_height_mm=bounds.min_height_mm,
    )
    cities = layout.cities_rect
    assert (1 - cities.y - cities.height) * bounds.min_height_mm >= 10
