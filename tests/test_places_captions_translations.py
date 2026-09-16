import pytest

from photoalbum.i18n import Translator


PLAIN_KEYS = (
    "tab.places_captions",
    "photos.places.search",
    "photos.places.search_placeholder",
    "photos.places.column.photo",
    "photos.places.column.date",
    "photos.places.column.location_caption",
    "photos.places.column.edit",
    "photos.places.caption",
    "photos.places.free_location",
    "photos.places.free_location_prompt",
    "photos.places.fix_in_photos",
)


@pytest.mark.parametrize("language", ("en", "fr"))
def test_places_captions_plain_keys_are_translated(
    language,
):
    translator = Translator(language)

    for key in PLAIN_KEYS:
        assert translator.tr(key) != key


@pytest.mark.parametrize("language", ("en", "fr"))
def test_places_captions_group_labels_are_translated(
    language,
):
    translator = Translator(language)

    year = translator.tr(
        "photos.places.year_group",
        year=2025,
        count=10,
    )
    month = translator.tr(
        "photos.places.month_group",
        month=translator.month_name(7),
        count=4,
    )

    assert "photos.places." not in year
    assert "photos.places." not in month
    assert "2025" in year
    assert translator.month_name(7) in month


def test_places_captions_french_labels():
    translator = Translator("fr")

    assert (
        translator.tr("tab.places_captions")
        == "Lieux et légendes"
    )
    assert (
        translator.tr(
            "photos.places.column.location_caption"
        )
        == "Lieu et légende"
    )
    assert translator.month_name(7) == "juillet"
