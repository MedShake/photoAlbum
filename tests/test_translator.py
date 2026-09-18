import pytest

from photoalbum.i18n import Translator


def test_english_translation():
    translator = Translator("en")

    assert translator.tr("plan.summary") == "Summary"


def test_french_translation():
    translator = Translator("fr")

    assert translator.tr("plan.summary") == "Résumé"


def test_translation_formats_values():
    translator = Translator("fr")

    assert translator.tr(
        "plan.unused_slots",
        count=3,
    ) == "3 emplacements inutilisés"


def test_month_name_is_controlled_by_application_language():
    assert Translator("en").month_name(3) == "March"
    assert Translator("fr").month_name(3) == "mars"


def test_unknown_key_returns_key():
    translator = Translator("fr")

    assert translator.tr("unknown.key") == "unknown.key"


def test_invalid_language_is_rejected():
    translator = Translator()

    with pytest.raises(ValueError):
        translator.set_language("xx")

def test_print_diagnostic_uses_real_singular_and_plural():
    en = Translator("en")
    fr = Translator("fr")

    assert en.tr(
        "plan.print_incompatible_one",
        pages=5,
        multiple=4,
        additional=1,
    ).endswith(
        "1 additional page would be required."
    )

    assert en.tr(
        "plan.print_incompatible_many",
        pages=6,
        multiple=4,
        additional=2,
    ).endswith(
        "2 additional pages would be required."
    )

    assert fr.tr(
        "plan.print_incompatible_one",
        pages=5,
        multiple=4,
        additional=1,
    ).endswith(
        "1 page supplémentaire serait nécessaire."
    )

    assert fr.tr(
        "plan.print_incompatible_many",
        pages=6,
        multiple=4,
        additional=2,
    ).endswith(
        "2 pages supplémentaires seraient nécessaires."
    )


def test_french_caption_overflow_wording():
    fr = Translator("fr")

    text = fr.tr(
        "plan.caption_overflow",
        page=12,
        photo="photo.jpg",
        required=4,
        available=2,
    )

    assert (
        "mais ce modèle n’en affiche au maximum que 2"
        in text
    )
