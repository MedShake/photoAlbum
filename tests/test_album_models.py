import pytest

from photoalbum.album import (
    A4,
    A5,
    US_LETTER,
    CoverPosition,
    page_format_from_id,
    PrintProfile,
)


def test_a4_format():
    assert A4.name == "A4"
    assert A4.width_mm == 210.0
    assert A4.height_mm == 297.0


def test_us_letter_format():
    assert US_LETTER.name == "US Letter"
    assert US_LETTER.width_mm == 215.9
    assert US_LETTER.height_mm == 279.4


def test_default_print_profile_uses_a4():
    profile = PrintProfile(
        name="Default",
    )

    assert profile.page_format == A4


def test_default_print_profile_targets_300_ppi():
    profile = PrintProfile(
        name="Default",
    )

    assert profile.target_ppi == 300


def test_print_profile_can_require_page_count_multiple():
    profile = PrintProfile(
        name="Print service",
        page_count_multiple=4,
    )

    assert profile.page_count_multiple == 4


def test_cover_positions_define_four_covers():
    assert set(CoverPosition) == {
        CoverPosition.FRONT,
        CoverPosition.INSIDE_FRONT,
        CoverPosition.INSIDE_BACK,
        CoverPosition.BACK,
    }


def test_page_format_from_id():
    assert page_format_from_id("a4") == A4
    assert page_format_from_id("a5") == A5
    assert page_format_from_id("us-letter") == US_LETTER


def test_unknown_page_format_is_rejected():
    with pytest.raises(
        ValueError,
        match="Unsupported page format",
    ):
        page_format_from_id("unknown")
