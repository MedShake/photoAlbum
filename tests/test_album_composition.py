from datetime import datetime
from pathlib import Path

import pytest

from photoalbum.album.composition import (
    ImageFit,
    NormalizedRect,
    PageComposer,
)
from photoalbum.album import (
    AutomaticPhotoPageSettings,
    BlankPageReason,
    PageSide,
    PhotoPageSettings,
    PlanItemKind,
    PlannedPage,
)
from photoalbum.models import Photo


def make_photo(name: str) -> Photo:
    return Photo(
        path=Path("/photos") / name,
        filename=name,
    )


def make_photo_page(
    capacity: int,
    photo_count: int | None = None,
) -> PlannedPage:
    if photo_count is None:
        photo_count = capacity

    photos = tuple(
        make_photo(f"photo-{index}.jpg")
        for index in range(photo_count)
    )

    return PlannedPage(
        number=1,
        side=PageSide.RIGHT,
        kind=PlanItemKind.PHOTO_GROUP,
        template_id=f"photo-page-{capacity}",
        photos=photos,
        photo_capacity=capacity,
    )


def test_normalized_rect_rejects_page_overflow():
    with pytest.raises(ValueError):
        NormalizedRect(
            x=0.8,
            y=0.1,
            width=0.3,
            height=0.5,
        )


def test_photo_slot_contains_image_and_caption_areas():
    photo = make_photo("photo.jpg")
    photo.capture_datetime = datetime(
        2025,
        7,
        14,
        18,
        30,
    )

    page = PlannedPage(
        number=1,
        side=PageSide.RIGHT,
        kind=PlanItemKind.PHOTO_GROUP,
        template_id="photo-page-1",
        photos=(photo,),
        photo_capacity=1,
    )

    composition = PageComposer().compose(page)

    slot = composition.photo_slots[0]

    assert slot.image_rect.height > 0
    assert slot.caption_rect is not None
    assert slot.caption_rect.height > 0

    assert (
        slot.image_rect.y
        < slot.caption_rect.y
    )

    assert slot.image_fit == ImageFit.CONTAIN


def test_two_photo_layout_is_vertical():
    composition = PageComposer().compose(
        make_photo_page(2)
    )

    first, second = composition.photo_slots

    assert (
        first.image_rect.y
        < second.image_rect.y
    )

    assert (
        first.image_rect.x
        == second.image_rect.x
    )


def test_four_photo_layout_is_two_by_two():
    composition = PageComposer().compose(
        make_photo_page(4)
    )

    assert len(composition.photo_slots) == 4

    assert (
        composition.photo_slots[0].image_rect.y
        == composition.photo_slots[1].image_rect.y
    )

    assert (
        composition.photo_slots[0].image_rect.x
        < composition.photo_slots[1].image_rect.x
    )


def test_three_photo_template_has_editorial_layout():
    composition = PageComposer().compose(
        make_photo_page(3)
    )

    assert len(composition.photo_slots) == 3

    top = composition.photo_slots[0].image_rect
    bottom_left = composition.photo_slots[1].image_rect
    bottom_right = composition.photo_slots[2].image_rect

    assert top.width > bottom_left.width
    assert bottom_left.y > top.y
    assert bottom_left.y == bottom_right.y


def test_unknown_photo_template_requires_registered_layout():
    page = PlannedPage(
        number=1,
        side=PageSide.RIGHT,
        kind=PlanItemKind.PHOTO_GROUP,
        template_id="third-party-template",
        photos=(make_photo("photo.jpg"),),
        photo_capacity=1,
    )

    with pytest.raises(KeyError):
        PageComposer().compose(page)


def test_unused_slots_are_preserved_in_composition():
    page = make_photo_page(
        capacity=4,
        photo_count=3,
    )

    composition = PageComposer().compose(page)

    assert len(composition.photo_slots) == 4
    assert len(composition.page.photos) == 3


def test_non_photo_page_has_no_photo_slots():
    page = PlannedPage(
        number=1,
        side=PageSide.RIGHT,
        kind=PlanItemKind.MONTH_DIVIDER,
        template_id="month-divider-classic",
        year=2025,
        month=3,
    )

    composition = PageComposer().compose(page)

    assert composition.photo_slots == ()

def test_technical_blank_composes_with_automatic_photo_page_settings():
    page = PlannedPage(
        number=2,
        side=PageSide.LEFT,
        kind=None,
        template_id="photo-page-2",
        photo_capacity=2,
        blank_reason=BlankPageReason.TECHNICAL,
    )
    photo_settings = PhotoPageSettings(
        automatic_mode=AutomaticPhotoPageSettings(
            "msb-orientation-1-2"
        )
    )

    composition = PageComposer().compose(
        page,
        photo_settings,
    )

    assert composition.page == page
    assert len(composition.photo_slots) == 2

