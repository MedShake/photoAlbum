"""Regression checks for the compact Album Settings accordion summaries.

Run with QT_QPA_PLATFORM=offscreen on Linux without a desktop session.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.i18n import Translator
from photoalbum.template_engine import create_template_registry


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app):
    widget = AlbumSettingsWidget(create_template_registry(), Translator("fr"))
    yield widget
    widget.close()


def _summary(view: AlbumSettingsWidget, key: str) -> str:
    return view._accordions.sections[key]._summary.text()


def test_page_format_summary_tracks_custom_format_and_collapse(view, app):
    """Format and orientation changes bypass the generic settings signal."""
    format_section = view._accordions.sections["format"]
    format_section.set_expanded(True)

    view._page_format_combo.setCurrentIndex(view._page_format_combo.findData("custom"))
    view._custom_width_spin.setValue(345.5)
    view._custom_height_spin.setValue(123.25)
    # The summary describes the applied format, not values being edited.
    assert "210 × 297 mm" in _summary(view, "format")
    view._custom_apply_button.click()
    app.processEvents()
    format_section.set_expanded(False)
    assert "345.5 × 123.25 mm" in _summary(view, "format")
    assert "Paysage" in _summary(view, "format")

    # Switching back to a standard format must not leave custom values behind.
    standard_index = view._page_format_combo.findData("a4")
    assert standard_index >= 0
    view._page_format_combo.setCurrentIndex(standard_index)
    app.processEvents()
    assert "345.5" not in _summary(view, "format")
    assert "A4" in _summary(view, "format")
    view._orientation_combo.setCurrentIndex(view._orientation_combo.findData("landscape"))
    assert _summary(view, "format") == "A4 — 297 × 210 mm · Paysage"


def test_format_header_is_short_and_square_summary_never_shows_orientation(view, app):
    section = view._accordions.sections["format"]
    assert section._heading.text() == "Format"
    # The full label can remain inside the expanded form.
    assert view._page_format_combo.count() > 0
    section.set_expanded(True)
    view._page_format_combo.setCurrentIndex(view._page_format_combo.findData("custom"))
    view._custom_width_spin.setValue(180)
    view._custom_height_spin.setValue(180)
    view._custom_apply_button.click()
    section.set_expanded(False)
    app.processEvents()
    assert _summary(view, "format") == "Personnalisé — 180 × 180 mm · Carré"
    assert "Portrait" not in _summary(view, "format")
    assert "Paysage" not in _summary(view, "format")

    section.set_expanded(True)
    view._custom_height_spin.setValue(181)
    view._custom_apply_button.click()
    section.set_expanded(False)
    assert "Carré" not in _summary(view, "format")
    assert "Portrait" in _summary(view, "format")


def test_covers_do_not_show_partial_model_names(view):
    view._accordions.sections["covers"].set_expanded(False)
    assert _summary(view, "covers") == ""
    assert not view._accordions.sections["covers"]._summary.isVisible()
    # The four selectors remain available when the accordion is opened.
    view._accordions.sections["covers"].set_expanded(True)
    assert all(combo.count() > 0 for combo in (
        view._front_cover_combo,
        view._inside_front_cover_combo,
        view._inside_back_cover_combo,
        view._back_cover_combo,
    ))


def test_dividers_show_active_and_inactive_groups_and_refresh(view):
    day = view._day_dividers_checkbox
    month = view._month_dividers_checkbox
    year = view._year_dividers_checkbox
    day.setChecked(True)
    month.setChecked(False)
    year.setChecked(True)
    view._accordions.sections["dividers"].set_expanded(False)
    assert _summary(view, "dividers") == "Actifs : Jour, Année · Inactifs : Mois"

    day.setChecked(False)
    month.setChecked(True)
    year.setChecked(False)
    assert _summary(view, "dividers") == "Actifs : Mois · Inactifs : Jour, Année"

    day.setChecked(True)
    year.setChecked(True)
    assert _summary(view, "dividers") == "Actifs : Jour, Mois, Année"

    day.setChecked(False)
    month.setChecked(False)
    year.setChecked(False)
    assert _summary(view, "dividers") == "Inactifs : Jour, Mois, Année"


def test_numbering_and_printing_share_one_section_and_keep_settings(view):
    sections = view._accordions.sections
    assert len(sections) == 7
    assert "numbering_printing" in sections
    assert "numbers" not in sections and "printing" not in sections
    assert sections["numbering_printing"]._heading.text() == "Numérotation"

    view._page_numbers_checkbox.setChecked(False)
    view._page_multiple_4_checkbox.setChecked(True)
    sections["numbering_printing"].set_expanded(False)
    assert _summary(view, "numbering_printing") == ""
    assert sections["numbering_printing"]._summary.isHidden()
    snapshot = view.settings()
    view.set_settings(snapshot)
    assert not view._page_numbers_checkbox.isChecked()
    assert view._page_multiple_4_checkbox.isChecked()
    assert _summary(view, "numbering_printing") == ""


def test_special_page_summaries_are_plural_and_disappear_when_empty(view):
    assert _summary(view, "front") == ""
    assert _summary(view, "back") == ""

    view._add_special_page(view._front_matter_list, view._front_matter_combo)
    assert _summary(view, "front") == "1 page configurée"
    assert _summary(view, "back") == ""

    view._add_special_page(view._front_matter_list, view._front_matter_combo)
    assert _summary(view, "front") == "2 pages configurées"

    view._add_special_page(view._back_matter_list, view._back_matter_combo)
    assert _summary(view, "back") == "1 page configurée"

    view.reset_to_defaults()
    assert _summary(view, "front") == ""
    assert _summary(view, "back") == ""


def test_english_labels_use_translator(app):
    view = AlbumSettingsWidget(create_template_registry(), Translator("en"))
    try:
        assert "Active:" in _summary(view, "dividers") or "Inactive:" in _summary(view, "dividers")
        assert "Day" in _summary(view, "dividers")
        assert view._accordions.sections["format"]._heading.text() == "Format"
        view._add_special_page(view._front_matter_list, view._front_matter_combo)
        assert _summary(view, "front") == "1 page configured"
        assert view._accordions.sections["numbering_printing"]._heading.text() == "Page numbering"
        assert _summary(view, "numbering_printing") == ""
        view._page_format_combo.setCurrentIndex(view._page_format_combo.findData("custom"))
        view._custom_width_spin.setValue(180)
        view._custom_height_spin.setValue(180)
        view._custom_apply_button.click()
        view._accordions.sections["format"].set_expanded(False)
        assert _summary(view, "format") == "Custom — 180 × 180 mm · Square"
    finally:
        view.close()
