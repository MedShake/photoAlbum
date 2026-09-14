from datetime import datetime
from pathlib import Path

from photoalbum.album import (
    PageNumberSettings,
    PageSide,
    PhotoCaptionSettings,
    PhotoPageSettings,
    PlanItemKind,
    PlannedPage,
)
from photoalbum.album.composition import (
    HorizontalAlignment,
    PageComposer,
    build_photo_caption,
    photo_location_text,
)
from photoalbum.models import Photo


def make_photo(
    name: str = "photo.jpg",
    *,
    with_date: bool = False,
    place_name: str | None = None,
    city: str | None = None,
    address: str | None = None,
) -> Photo:
    return Photo(
        path=Path("/photos") / name,
        filename=name,
        capture_datetime=(
            datetime(2025, 7, 14, 18, 30)
            if with_date
            else None
        ),
        place_name=place_name,
        city=city,
        address=address,
    )


def make_page(
    photos: tuple[Photo, ...],
    *,
    capacity: int = 2,
    side: PageSide = PageSide.RIGHT,
) -> PlannedPage:
    return PlannedPage(
        number=7,
        side=side,
        kind=PlanItemKind.PHOTO_GROUP,
        template_id=f"photo-page-{capacity}",
        photos=photos,
        photo_capacity=capacity,
    )


def settings(
    *,
    show_datetime: bool,
    show_location: bool,
) -> PhotoPageSettings:
    return PhotoPageSettings(
        template_id="photo-page-2",
        caption=PhotoCaptionSettings(
            show_datetime=show_datetime,
            show_location=show_location,
        ),
    )


def test_no_caption_options_use_full_photo_cell():
    page = make_page(
        (make_photo(with_date=True, city="Paris"),)
    )

    composition = PageComposer().compose(
        page,
        settings(
            show_datetime=False,
            show_location=False,
        ),
        PageNumberSettings(enabled=False),
    )

    slot = composition.photo_slots[0]

    assert slot.caption.is_empty
    assert slot.caption_rect is None


def test_requested_missing_location_does_not_create_caption():
    page = make_page(
        (make_photo(),)
    )

    composition = PageComposer().compose(
        page,
        settings(
            show_datetime=False,
            show_location=True,
        ),
        PageNumberSettings(enabled=False),
    )

    slot = composition.photo_slots[0]

    assert slot.caption.location_text is None
    assert slot.caption_rect is None


def test_date_only_uses_one_caption_line():
    photo = make_photo(with_date=True)

    caption = build_photo_caption(
        photo,
        settings(
            show_datetime=True,
            show_location=False,
        ),
    )

    assert caption.capture_datetime is not None
    assert caption.location_text is None
    assert caption.line_count == 1


def test_date_and_location_use_two_lines():
    photo = make_photo(
        with_date=True,
        city="Paris",
    )

    caption = build_photo_caption(
        photo,
        settings(
            show_datetime=True,
            show_location=True,
        ),
    )

    assert caption.line_count == 2


def test_location_prefers_place_and_city():
    photo = make_photo(
        place_name="Tour Eiffel",
        city="Paris",
        address="5 Avenue Anatole France",
    )

    assert (
        photo_location_text(photo)
        == "Tour Eiffel, Paris"
    )


def test_location_uses_address_as_last_fallback():
    photo = make_photo(
        address="5 Avenue Anatole France"
    )

    assert (
        photo_location_text(photo)
        == "5 Avenue Anatole France"
    )


def test_same_row_keeps_images_aligned():
    first = make_photo(
        "one.jpg",
        with_date=True,
        city="Paris",
    )
    second = make_photo(
        "two.jpg",
        with_date=True,
    )

    page = make_page(
        (first, second),
        capacity=4,
    )

    composition = PageComposer().compose(
        page,
        settings(
            show_datetime=True,
            show_location=True,
        ),
        PageNumberSettings(enabled=False),
    )

    first_slot = composition.photo_slots[0]
    second_slot = composition.photo_slots[1]

    assert (
        first_slot.image_rect.height
        == second_slot.image_rect.height
    )

    assert first_slot.caption.line_count == 2
    assert second_slot.caption.line_count == 1


def test_page_number_can_be_disabled():
    page = make_page(
        (make_photo(),),
    )

    composition = PageComposer().compose(
        page,
        page_numbers=PageNumberSettings(
            enabled=False
        ),
    )

    assert composition.page_number is None


def test_right_page_number_is_right_aligned():
    page = make_page(
        (make_photo(),),
        side=PageSide.RIGHT,
    )

    composition = PageComposer().compose(page)

    assert composition.page_number is not None
    assert (
        composition.page_number.alignment
        == HorizontalAlignment.RIGHT
    )


def test_left_page_number_is_left_aligned():
    page = make_page(
        (make_photo(),),
        side=PageSide.LEFT,
    )

    composition = PageComposer().compose(page)

    assert composition.page_number is not None
    assert (
        composition.page_number.alignment
        == HorizontalAlignment.LEFT
    )
