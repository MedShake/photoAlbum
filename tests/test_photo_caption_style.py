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

def test_canonical_caption_wrap_is_deterministic():
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        QApplication([])
    from photoalbum.templates.msb.photo_page.caption_layout import wrap_text

    settings = {"photo_caption": {"font_size": 8.0}}
    text = "Avenue de l'Île, Plaisance, Orvault, Nantes, Loire-Atlantique"
    first = wrap_text(text, width_mm=45.0, settings=settings)
    second = wrap_text(text, width_mm=45.0, settings=settings)

    assert first == second
    assert " ".join(first) == text
    assert len(first) >= 2


def test_canonical_caption_wrap_splits_a_single_oversized_block():
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        QApplication([])
    from photoalbum.templates.msb.photo_page.caption_layout import wrap_text

    settings = {"photo_caption": {"font_size": 8.0}}
    text = "UnBlocSansAucunEspaceQuiEstVraimentBeaucoupTropLongPourLaZone"
    lines = wrap_text(text, width_mm=20.0, settings=settings)

    assert len(lines) > 1
    assert "".join(lines) == text



def test_physical_caption_line_height_follows_font_size():
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        QApplication([])

    from photoalbum.templates.msb.photo_page.caption_layout import (
        physical_line_height_mm,
    )

    small = physical_line_height_mm(
        {
            "photo_caption": {
                "font_size": 8.0,
            }
        }
    )

    large = physical_line_height_mm(
        {
            "photo_caption": {
                "font_size": 20.0,
            }
        }
    )

    assert small > 0.0
    assert large > small



def test_photo_settings_preview_does_not_own_page_geometry():
    """Settings preview must use canonical composition geometry."""
    from pathlib import Path

    path = (
        Path(__file__).parents[1]
        / "src/photoalbum/templates/msb/photo_page/settings.py"
    )
    source = path.read_text(encoding="utf-8")

    assert "PageComposer" in source
    assert "PhotoPageWidgetRenderer" in source

    forbidden = (
        "margin = 24",
        "gap = 12",
        "cell_width =",
        "cell_height =",
        "caption_height =",
        "image_height =",
    )

    for fragment in forbidden:
        assert fragment not in source
