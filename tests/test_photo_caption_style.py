from photoalbum.templates.msb.photo_page.caption_style import (
    DEFAULT_CAPTION_ORDER,
    caption_lines,
    caption_order,
)


def test_default_caption_order():
    assert caption_order({}) == DEFAULT_CAPTION_ORDER


def test_default_caption_lines():
    assert caption_lines(
        caption_text="Une légende",
        capture_datetime_text="18/09/2026 10:30",
        location_text="Paris",
        settings={},
    ) == [
        "Une légende — 18/09/2026 10:30",
        "Paris",
    ]


def test_break_can_be_moved():
    settings = {
        "photo_caption": {
            "order": [
                "location",
                "break",
                "caption",
                "datetime",
            ]
        }
    }

    assert caption_lines(
        caption_text="Une légende",
        capture_datetime_text="18/09/2026 10:30",
        location_text="Paris",
        settings=settings,
    ) == [
        "Paris",
        "Une légende — 18/09/2026 10:30",
    ]


def test_disabled_item_keeps_order():
    settings = {
        "photo_caption": {
            "show_location": False,
            "order": [
                "location",
                "break",
                "caption",
                "datetime",
            ],
        }
    }

    assert caption_order(settings) == (
        "location",
        "break",
        "caption",
        "datetime",
    )

    assert caption_lines(
        caption_text="Une légende",
        capture_datetime_text="18/09/2026 10:30",
        location_text="Paris",
        settings=settings,
    ) == [
        "Une légende — 18/09/2026 10:30",
    ]


def test_break_after_all_items_gives_one_line():
    settings = {
        "photo_caption": {
            "order": [
                "caption",
                "datetime",
                "location",
                "break",
            ]
        }
    }

    assert caption_lines(
        caption_text="Une légende",
        capture_datetime_text="18/09/2026 10:30",
        location_text="Paris",
        settings=settings,
    ) == [
        "Une légende — 18/09/2026 10:30 — Paris",
    ]
