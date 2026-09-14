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
    ) == "3 emplacement(s) inutilisé(s)"


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

