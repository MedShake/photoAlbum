"""Offscreen Qt integration tests executed from the Photo Album repository.

QT_QPA_PLATFORM=offscreen pytest -q src/photoalbum/templates/complex/qa/test_complex_pack.py
"""
from datetime import datetime
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from photoalbum.album import AutomaticPhotoPageContext, PageInstance, PageNumberSettings
from photoalbum.album.composition import ImageFit, TemplateLayoutRegistry
from photoalbum.album.pagination import PlannedPage, PageSide
from photoalbum.album.planning import PlanItemKind
from photoalbum.models import Photo
from photoalbum.template_engine.discovery import create_template_registry
from photoalbum.templates.complex.photo_page.layout import register_layouts
from photoalbum.templates.complex.photo_page.automatic import select_automatic_1_5
from photoalbum.templates.complex.photo_page.variants import variants_for


def photo(index, orientation):
    width, height = ((3000, 4000) if orientation == "P" else (4000, 3000))
    return Photo(path=Path(f"/tmp/complex-image-{index}.jpg"),
                 filename=f"complex-image-{index}.jpg", width=width,
                 height=height, capture_datetime=datetime(2025, 1, index + 1),
                 caption=f"Photo {index}")


@pytest.mark.parametrize("width,height,family", [
    (210, 297, "portrait"), (297, 210, "landscape"), (210, 210, "square")
])
def test_layouts_and_image_fit(width, height, family):
    QApplication.instance() or QApplication([])
    registry = TemplateLayoutRegistry()
    register_layouts(registry)
    expected = {3:2,4:3,5:(2 if family == "square" else 5)}
    for capacity in range(1,6):
        options = variants_for(capacity,width,height)
        if capacity in expected:
            assert len(options) == expected[capacity]
        else:
            assert not options
        for variant in options or (None,):
            settings = {"layout_variant": variant} if variant else {}
            inst = PageInstance(f"complex-photo-{capacity}", settings=settings)
            photos = tuple(photo(i, "L") for i in range(capacity))
            page = PlannedPage(number=3, side=PageSide.RIGHT,
                               kind=PlanItemKind.PHOTO_GROUP,
                               template_id=inst.template_id, photos=photos,
                               photo_capacity=capacity, page_instance=inst)
            comp = registry.get(inst.template_id).compose(
                page, inst, PageNumberSettings(enabled=False),
                page_width_mm=width, page_height_mm=height)
            assert len(comp.photo_slots) == capacity
            for slot in comp.photo_slots:
                assert slot.image_fit is ImageFit.CONTAIN
                assert slot.image_rect.x >= 0 and slot.image_rect.y >= 0
                assert slot.image_rect.x+slot.image_rect.width <= 1.0000001
                assert slot.image_rect.y+slot.image_rect.height <= 1.0000001
                assert slot.caption_rect is not None
                assert slot.caption_rect.y+slot.caption_rect.height <= 1.0000001


def test_square_only_has_the_two_mosaics():
    from photoalbum.templates.complex.photo_page.layout import _rects_for
    assert variants_for(5,210,210) == ("mosaic", "mosaic-mirror")
    for banned in ("sequence", "sequence-top", "sequence-bottom"):
        assert _rects_for(5,210,210,{"layout_variant":banned}) == _rects_for(5,210,210,{"layout_variant":"mosaic"})


@pytest.mark.parametrize("dims,orientations,expected,variant", [
    ((210, 297), "PPLPL", "complex-photo-5", "mosaic"),
    ((297, 210), "PPPLL", "complex-photo-5", "mosaic"),
    ((210, 210), "PPLPL", "complex-photo-5", "mosaic"),
    ((210, 297), "LLLLL", "complex-photo-5", "sequence"),
    ((297, 210), "LLLLL", "complex-photo-5", "sequence"),
    ((210, 297), "PLLLL", "complex-photo-4", "reportage"),
    ((297, 210), "LPLLL", "complex-photo-4", "reportage-top-left"),
])
def test_automatic_mode(dims,orientations,expected,variant):
    context=AutomaticPhotoPageContext(
        photos=tuple(photo(i,s) for i,s in enumerate(orientations)),
        page_width_mm=dims[0],page_height_mm=dims[1])
    selected=select_automatic_1_5(context)
    assert isinstance(selected,PageInstance)
    assert selected.template_id==expected
    assert selected.settings["layout_variant"]==variant


def test_manifest_discovers_independent_pack():
    registry=create_template_registry()
    for n in range(1,6):
        assert registry.get(f"complex-photo-{n}").photo_capacity==n
    assert registry.get_automatic_photo_page_mode("complex-auto-1-5") is not None


def test_msb_not_loaded_by_complex_modules():
    import sys
    from photoalbum.templates.complex.photo_page import layout, settings, widget_renderer
    for module in (layout,settings,widget_renderer):
        assert not any("photoalbum.templates."+"msb" in str(value) for value in vars(module).values() if isinstance(value,str))
