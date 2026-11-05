"""Selector contracts using the real host models, without replacing modules."""
from collections import Counter
import json
from pathlib import Path

import pytest

from photoalbum.album import AutomaticPhotoPageContext, PageInstance
from photoalbum.models import Photo
from photoalbum.templates.complex.photo_page import automatic, variants


ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = {"portrait": (210, 297), "landscape": (297, 210), "square": (210, 210)}
PHOTO_DIMENSIONS = {"P": (3000, 4000), "L": (4000, 3000), "S": (4000, 4000)}
EXPECTED_FIVE = {
    "portrait": Counter({"PPPLL": 1, "PPLPL": 1, "PPLLP": 1, "PLLPP": 1, "LPLPP": 1, "LLPPP": 1, "LLLLL": 3}),
    "landscape": Counter({"PPPLL": 2, "PPLLP": 1, "PLLPP": 1, "LLPPP": 2, "LLLLL": 2}),
    "square": Counter({"PPLPL": 1, "PPLLP": 1, "PLPPL": 2, "PLPLP": 2, "PLLPP": 1, "LPPPL": 2, "LPPLP": 2, "LPLPP": 1}),
}
EXPECTED_FOUR = {
    "portrait": Counter({"PLLL": 1, "LPLL": 1, "LLPL": 1, "LLLP": 1}),
    "landscape": Counter({"PLLL": 2, "LLLP": 2}),
    "square": Counter({"PLLL": 1, "LLLP": 1}),
}


def choose(pattern, family, counts=None):
    photos = tuple(
        Photo(path=Path(f"/tmp/complex-selector-{i}.jpg"), filename=f"{i}.jpg",
              width=PHOTO_DIMENSIONS[orientation][0], height=PHOTO_DIMENSIONS[orientation][1])
        for i, orientation in enumerate(pattern)
    )
    selected = automatic.select_automatic_1_5(
        AutomaticPhotoPageContext(photos, *DIMENSIONS[family], counts)
    )
    if isinstance(selected, PageInstance):
        return selected.template_id, selected.settings.get("layout_variant")
    return selected, None


@pytest.mark.parametrize("family", DIMENSIONS)
@pytest.mark.parametrize("capacity,expected", [(4, EXPECTED_FOUR), (5, EXPECTED_FIVE)])
def test_signatures_and_per_signature_rotation(family, capacity, expected):
    width, height = DIMENSIONS[family]
    signatures = Counter(
        "".join(automatic.signature(capacity, name, family))
        for name in variants.variants_for(capacity, width, height)
    )
    assert signatures == expected[family]
    for signature, frequency in expected[family].items():
        options = automatic.compatible_options(capacity, family, tuple(signature))
        assert len(options) == frequency
        counts = {}
        for index in range(frequency * 3):
            assert choose(signature, family, counts) == (
                f"complex-photo-{capacity}", options[index % frequency]
            )
        assert counts == ({(family, signature): frequency * 3} if frequency > 1 else {})
        # Calls without host counters are reproducible and have no global state.
        assert choose(signature, family)[1] == options[0]
        assert choose(signature, family)[1] == options[0]


def test_rotation_does_not_advance_other_signatures():
    counts = {}
    assert [choose("LLLLL", "portrait", counts)[1] for _ in range(4)] == [
        "five-sequence-top", "five-sequence-center", "five-sequence-bottom", "five-sequence-top"
    ]
    assert choose("PPLPL", "portrait", counts)[1] == "five-mosaic-left"
    assert counts == {("portrait", "LLLLL"): 4}


@pytest.mark.parametrize("pattern,family,expected", [
    ("PLLLP", "portrait", "complex-photo-4"),
    ("PS", "landscape", "complex-photo-1"),
    ("LLLLL", "square", "complex-photo-2"),
    ("LPLL", "landscape", "complex-photo-1"),
])
def test_greedy_fallback_preserves_photo_order(pattern, family, expected):
    assert choose(pattern, family)[0] == expected


def test_manifest_declares_one_automatic_mode():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["automatic_photo_page_modes"]) == 1
    assert manifest["automatic_photo_page_modes"][0]["id"] == "complex-auto-1-5"
