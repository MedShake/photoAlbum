import pytest

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
) -> Photo:
    return Photo(
        path=Path("/photos") / name,
        filename=name,
        capture_datetime=(
            datetime(2025, 7, 14, 18, 30)
            if with_date
            else None
        ),
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
        (make_photo(with_date=True),)
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
    )
    photo.raw_location_data = {
        "address": {
            "city": "Paris",
        }
    }

    caption = build_photo_caption(
        photo,
        settings(
            show_datetime=True,
            show_location=True,
        ),
    )

    assert caption.line_count == 2


def test_location_uses_automatic_location_composition():
    photo = make_photo()
    photo.raw_location_data = {
        "address": {
            "tourism": "Tour Eiffel",
            "city": "Paris",
            "country": "France",
        }
    }

    assert (
        photo_location_text(photo)
        == "Tour Eiffel, Paris"
    )


def test_location_uses_editorial_text_when_edited():
    photo = make_photo()
    photo.raw_location_data = {
        "address": {
            "tourism": "Tour Eiffel",
            "city": "Paris",
        }
    }
    photo.location_selection_edited = True
    photo.location_text = "Champ de Mars"

    assert (
        photo_location_text(photo)
        == "Champ de Mars"
    )


def test_location_respects_explicit_empty_editorial_selection():
    photo = make_photo()
    photo.raw_location_data = {
        "address": {
            "tourism": "Tour Eiffel",
            "city": "Paris",
        }
    }
    photo.location_selection_edited = True
    photo.location_text = None

    assert photo_location_text(photo) is None


def test_same_row_keeps_images_aligned():
    first = make_photo(
        "one.jpg",
        with_date=True,
    )
    first.raw_location_data = {
        "address": {
            "city": "Paris",
        }
    }

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



def test_custom_layout_can_reserve_more_than_three_caption_lines():
    """Caption capacity belongs to the template, not the engine."""
    from photoalbum.album.composition import (
        NormalizedRect,
        PhotoCaptionContent,
        PhotoTemplateLayout,
    )

    layout = PhotoTemplateLayout(
        cells_factory=lambda _w, _h: (
            NormalizedRect(
                x=0.1,
                y=0.1,
                width=0.8,
                height=0.8,
            ),
        ),
        max_caption_lines=10,
    )

    caption = PhotoCaptionContent(
        caption_text="caption",
        location_text="location",
    )

    rows = layout._row_caption_lines(
        (caption,),
        layout.cells_factory(
            210.0,
            297.0,
        ),
    )

    assert layout.max_caption_lines == 10

    # Two logical lines need two lines, not the complete
    # ten-line capacity of the template.
    assert next(iter(rows.values())) == 2

def test_builtin_photo_layouts_limit_reserved_caption_height_to_three_lines():
    from photoalbum.album.composition import create_builtin_layout_registry

    registry = create_builtin_layout_registry()

    for template_id in (
        "photo-page-1",
        "photo-page-2",
        "photo-page-3",
        "photo-page-4",
    ):
        assert registry.get(template_id).max_caption_lines == 3


def test_caption_row_reserves_largest_actual_requirement():
    """A row follows its largest real caption requirement."""
    from photoalbum.album.composition import (
        NormalizedRect,
        PhotoCaptionContent,
        PhotoTemplateLayout,
    )

    layout = PhotoTemplateLayout(
        cells_factory=lambda _w, _h: (
            NormalizedRect(
                x=0.1,
                y=0.1,
                width=0.35,
                height=0.8,
            ),
            NormalizedRect(
                x=0.55,
                y=0.1,
                width=0.35,
                height=0.8,
            ),
        ),
        max_caption_lines=3,
    )

    one_line = PhotoCaptionContent(
        caption_text="Courte légende",
    )

    two_lines = PhotoCaptionContent(
        caption_text="Légende",
        location_text="Lieu",
    )

    rows = layout._row_caption_lines(
        (one_line, two_lines),
        layout.cells_factory(
            210.0,
            297.0,
        ),
    )

    assert len(rows) == 1
    assert next(iter(rows.values())) == 2

def test_builtin_two_photo_layout_keeps_vertical_gap():
    from photoalbum.album.composition import (
        create_builtin_layout_registry,
    )

    layout = create_builtin_layout_registry().get(
        "photo-page-2"
    )
    cells = layout.cells_factory(
        210.0,
        297.0,
    )

    assert len(cells) == 2

    first_bottom = (
        cells[0].y + cells[0].height
    )
    second_top = cells[1].y

    gap_mm = (
        second_top - first_bottom
    ) * 297.0

    assert gap_mm == pytest.approx(
        4.0,
        abs=0.01,
    )

@pytest.mark.parametrize("capacity", [1, 2, 3, 4])
def test_builtin_photo_layout_has_fixed_footer_clearance(
    capacity,
):
    from photoalbum.album.composition import (
        create_builtin_layout_registry,
    )

    layout = create_builtin_layout_registry().get(
        f"photo-page-{capacity}"
    )

    cells = layout.cells_factory(
        210.0,
        297.0,
    )

    content_bottom = max(
        cell.y + cell.height
        for cell in cells
    )

    # Built-in MSB photo pages reserve 12 mm at the bottom.
    assert content_bottom == pytest.approx(
        1.0 - 12.0 / 297.0,
        abs=1e-6,
    )

    # The page-number box starts at y=.965.
    # Content must finish before it.
    assert content_bottom < layout.page_number_y


@pytest.mark.parametrize("capacity", [1, 2, 3, 4])
def test_three_line_caption_stays_above_page_number(
    capacity,
):
    photos = tuple(
        make_photo(
            f"photo-{index}.jpg",
            with_date=True,
        )
        for index in range(capacity)
    )

    page = make_page(
        photos,
        capacity=capacity,
    )

    settings = PhotoPageSettings(
        template_id=f"photo-page-{capacity}",
        caption=PhotoCaptionSettings(
            show_datetime=True,
            show_location=True,
        ),
    )

    composition = PageComposer().compose(
        page,
        settings,
        PageNumberSettings(enabled=True),
    )

    assert composition.page_number is not None

    footer_top = composition.page_number.rect.y

    for slot in composition.photo_slots:
        if slot.caption_rect is None:
            continue

        caption_bottom = (
            slot.caption_rect.y
            + slot.caption_rect.height
        )

        assert caption_bottom < footer_top


@pytest.mark.parametrize("capacity", [1, 2, 3, 4])
def test_page_number_toggle_does_not_reflow_photo_geometry(
    capacity,
):
    photos = tuple(
        make_photo(
            f"photo-{index}.jpg",
            with_date=True,
        )
        for index in range(capacity)
    )

    page = make_page(
        photos,
        capacity=capacity,
    )

    settings = PhotoPageSettings(
        template_id=f"photo-page-{capacity}",
        caption=PhotoCaptionSettings(
            show_datetime=True,
            show_location=True,
        ),
    )

    with_number = PageComposer().compose(
        page,
        settings,
        PageNumberSettings(enabled=True),
    )

    without_number = PageComposer().compose(
        page,
        settings,
        PageNumberSettings(enabled=False),
    )

    assert (
        with_number.photo_slots
        == without_number.photo_slots
    )


def test_captionless_row_gives_complete_cell_to_image():
    from photoalbum.album.composition import (
        NormalizedRect,
        PhotoCaptionContent,
        PhotoTemplateLayout,
    )

    cell = NormalizedRect(
        x=0.1,
        y=0.1,
        width=0.8,
        height=0.7,
    )

    layout = PhotoTemplateLayout(
        cells_factory=lambda _w, _h: (cell,),
        max_caption_lines=3,
    )

    rows = layout._row_caption_lines(
        (PhotoCaptionContent(),),
        (cell,),
    )

    key = layout._row_key(cell)

    assert rows[key] == 0
    assert not layout._row_has_caption(
        row_key=key,
        row_caption_lines=rows,
    )

    slot = layout._compose_slot(
        cell=cell,
        caption=PhotoCaptionContent(),
        reserved_lines=rows[key],
        page_height_mm=297.0,
    )

    assert slot.caption_rect is None
    assert slot.image_rect == cell



def test_one_caption_reserves_actual_requirement_for_entire_row():
    from photoalbum.album.composition import (
        NormalizedRect,
        PhotoCaptionContent,
        PhotoTemplateLayout,
    )

    left = NormalizedRect(
        x=0.1,
        y=0.1,
        width=0.35,
        height=0.7,
    )

    right = NormalizedRect(
        x=0.55,
        y=0.1,
        width=0.35,
        height=0.7,
    )

    layout = PhotoTemplateLayout(
        cells_factory=lambda _w, _h: (
            left,
            right,
        ),
        max_caption_lines=3,
    )

    captions = (
        PhotoCaptionContent(),
        PhotoCaptionContent(
            caption_text="Visible caption",
        ),
    )

    rows = layout._row_caption_lines(
        captions,
        (left, right),
    )

    key = layout._row_key(left)

    assert rows[key] == 1

    left_slot = layout._compose_slot(
        cell=left,
        caption=captions[0],
        reserved_lines=rows[key],
        page_height_mm=297.0,
    )

    right_slot = layout._compose_slot(
        cell=right,
        caption=captions[1],
        reserved_lines=rows[key],
        page_height_mm=297.0,
    )

    assert (
        left_slot.image_rect.height
        == right_slot.image_rect.height
    )

@pytest.mark.parametrize(
    "capacity",
    [1, 2, 3, 4],
)
def test_builtin_page_without_captions_uses_complete_cells(
    capacity,
):
    from photoalbum.album.composition import (
        create_builtin_layout_registry,
    )

    photos = tuple(
        make_photo(
            f"no-caption-{index}.jpg",
            with_date=True,
        )
        for index in range(capacity)
    )

    page = make_page(
        photos,
        capacity=capacity,
    )

    photo_settings = PhotoPageSettings(
        template_id=f"photo-page-{capacity}",
        caption=PhotoCaptionSettings(
            show_datetime=False,
            show_location=False,
        ),
    )

    composition = PageComposer().compose(
        page,
        photo_settings,
        PageNumberSettings(enabled=True),
    )

    layout = create_builtin_layout_registry().get(
        f"photo-page-{capacity}"
    )

    cells = layout.cells_factory(
        210.0,
        297.0,
    )

    for slot, cell in zip(
        composition.photo_slots,
        cells,
    ):
        assert slot.caption.is_empty
        assert slot.caption_rect is None
        assert slot.image_rect == cell



def test_captionless_and_captioned_rows_are_independent():
    from photoalbum.album.composition import (
        NormalizedRect,
        PhotoCaptionContent,
        PhotoTemplateLayout,
    )

    cells = (
        NormalizedRect(
            x=0.1,
            y=0.1,
            width=0.8,
            height=0.35,
        ),
        NormalizedRect(
            x=0.1,
            y=0.55,
            width=0.8,
            height=0.35,
        ),
    )

    layout = PhotoTemplateLayout(
        cells_factory=lambda _w, _h: cells,
        max_caption_lines=3,
    )

    captions = (
        PhotoCaptionContent(),
        PhotoCaptionContent(
            caption_text="Caption",
        ),
    )

    rows = layout._row_caption_lines(
        captions,
        cells,
    )

    top_key = layout._row_key(
        cells[0]
    )
    bottom_key = layout._row_key(
        cells[1]
    )

    assert rows[top_key] == 0
    assert rows[bottom_key] == 1

    top = layout._compose_slot(
        cell=cells[0],
        caption=captions[0],
        reserved_lines=rows[top_key],
        page_height_mm=297.0,
    )

    bottom = layout._compose_slot(
        cell=cells[1],
        caption=captions[1],
        reserved_lines=rows[bottom_key],
        page_height_mm=297.0,
    )

    assert top.caption_rect is None
    assert top.image_rect == cells[0]

    assert bottom.caption_rect is not None
    assert (
        bottom.image_rect.height
        < cells[1].height
    )

def _spread_page(
    *,
    number,
    side,
    photos,
    template_id="photo-page-2",
    capacity=2,
):
    return PlannedPage(
        number=number,
        side=side,
        kind=PlanItemKind.PHOTO_GROUP,
        template_id=template_id,
        photos=tuple(photos),
        photo_capacity=capacity,
    )


def test_spread_without_any_caption_reserves_zero_lines():
    composer = PageComposer()

    left = _spread_page(
        number=2,
        side=PageSide.LEFT,
        photos=(make_photo("left.jpg"),),
    )
    right = _spread_page(
        number=3,
        side=PageSide.RIGHT,
        photos=(make_photo("right.jpg"),),
    )

    photo_settings = settings(
        show_datetime=False,
        show_location=False,
    )

    assert composer.spread_caption_lines(
        left,
        (left, right),
        photo_settings,
    ) == 0

    assert composer.spread_caption_lines(
        right,
        (left, right),
        photo_settings,
    ) == 0


def test_spread_caption_reserve_is_shared_by_facing_pages():
    composer = PageComposer()

    left = _spread_page(
        number=2,
        side=PageSide.LEFT,
        photos=(make_photo("left.jpg"),),
    )

    right = _spread_page(
        number=3,
        side=PageSide.RIGHT,
        photos=(
            make_photo(
                "right.jpg",
                with_date=True,
            ),
        ),
    )

    photo_settings = settings(
        show_datetime=True,
        show_location=False,
    )

    left_lines = composer.spread_caption_lines(
        left,
        (left, right),
        photo_settings,
    )
    right_lines = composer.spread_caption_lines(
        right,
        (left, right),
        photo_settings,
    )

    assert left_lines == right_lines
    assert left_lines >= 1


def test_spread_reserve_gives_facing_photos_same_height():
    composer = PageComposer()

    left = _spread_page(
        number=2,
        side=PageSide.LEFT,
        photos=(make_photo("left.jpg"),),
    )

    right = _spread_page(
        number=3,
        side=PageSide.RIGHT,
        photos=(
            make_photo(
                "right.jpg",
                with_date=True,
            ),
        ),
    )

    photo_settings = settings(
        show_datetime=True,
        show_location=False,
    )

    reserve = composer.spread_caption_lines(
        left,
        (left, right),
        photo_settings,
    )

    left_composition = composer.compose(
        left,
        photo_settings,
        PageNumberSettings(enabled=True),
        reserved_caption_lines=reserve,
    )

    right_composition = composer.compose(
        right,
        photo_settings,
        PageNumberSettings(enabled=True),
        reserved_caption_lines=reserve,
    )

    assert (
        left_composition.photo_slots[0].image_rect.height
        == right_composition.photo_slots[0].image_rect.height
    )



def test_spread_real_requirement_is_not_clipped_for_diagnostics():
    from photoalbum.album.composition import (
        NormalizedRect,
        PhotoTemplateLayout,
        TemplateLayoutRegistry,
    )

    registry = TemplateLayoutRegistry()

    layout = PhotoTemplateLayout(
        cells_factory=lambda _w, _h: (
            NormalizedRect(
                x=0.05,
                y=0.05,
                width=0.90,
                height=0.90,
            ),
        ),
        max_caption_lines=3,
        caption_line_counter=(
            lambda *_args, **_kwargs: 7
        ),
    )

    registry.register(
        "diagnostic-caption-layout",
        layout,
    )

    composer = PageComposer(
        registry
    )

    photo = make_photo(
        "long-caption.jpg",
        with_date=True,
    )

    page = _spread_page(
        number=2,
        side=PageSide.LEFT,
        photos=(photo,),
        template_id="diagnostic-caption-layout",
        capacity=1,
    )

    photo_settings = settings(
        show_datetime=True,
        show_location=True,
    )

    required = (
        composer.spread_required_caption_lines(
            page,
            (page,),
            photo_settings,
        )
    )

    reserved = composer.spread_caption_lines(
        page,
        (page,),
        photo_settings,
    )

    # Diagnostic keeps the real requirement.
    assert required == 7

    # Geometry obeys the template capacity.
    assert reserved == 3
    assert reserved < required

def test_zero_caption_spread_keeps_four_mm_interphoto_gap():
    composer = PageComposer()

    page = _spread_page(
        number=2,
        side=PageSide.LEFT,
        photos=(
            make_photo("one.jpg"),
            make_photo("two.jpg"),
        ),
    )

    photo_settings = settings(
        show_datetime=False,
        show_location=False,
    )

    reserve = composer.spread_caption_lines(
        page,
        (page,),
        photo_settings,
    )

    assert reserve == 0

    layout = composer._registry.get(
        "photo-page-2"
    )

    cells = layout.cells_factory(
        210.0,
        297.0,
    )

    gap_mm = (
        cells[1].y
        - (
            cells[0].y
            + cells[0].height
        )
    ) * 297.0

    assert gap_mm == pytest.approx(
        4.0,
        abs=0.01,
    )
