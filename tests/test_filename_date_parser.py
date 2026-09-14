from datetime import datetime

import pytest

from photoalbum.metadata import FilenameDateParser


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        (
            "2025-06-15.jpg",
            datetime(2025, 6, 15),
        ),
        (
            "2025_06_15.jpg",
            datetime(2025, 6, 15),
        ),
        (
            "2025.06.15.jpg",
            datetime(2025, 6, 15),
        ),
        (
            "IMG_2025-06-15.jpg",
            datetime(2025, 6, 15),
        ),
        (
            "20250615.jpg",
            datetime(2025, 6, 15),
        ),
        (
            "IMG_20250615.jpg",
            datetime(2025, 6, 15),
        ),
        (
            "2025-06-15_14-30-45.jpg",
            datetime(2025, 6, 15, 14, 30, 45),
        ),
        (
            "2025-06-15 14-30-45.jpg",
            datetime(2025, 6, 15, 14, 30, 45),
        ),
        (
            "2025-06-15T14:30:45.jpg",
            datetime(2025, 6, 15, 14, 30, 45),
        ),
        (
            "20250615_143045.jpg",
            datetime(2025, 6, 15, 14, 30, 45),
        ),
        (
            "IMG_20250615_143045.jpg",
            datetime(2025, 6, 15, 14, 30, 45),
        ),
    ],
)
def test_parse_supported_filename_dates(filename, expected):
    parser = FilenameDateParser()

    assert parser.parse(filename) == expected


@pytest.mark.parametrize(
    "filename",
    [
        "holiday.jpg",
        "IMG_1234.jpg",
        "15-06-2025.jpg",
        "06-15-2025.jpg",
        "2025-13-15.jpg",
        "2025-02-30.jpg",
        "20250699.jpg",
    ],
)
def test_reject_invalid_or_ambiguous_filename_dates(filename):
    parser = FilenameDateParser()

    assert parser.parse(filename) is None

