"""Regression checks for the native Album Settings page summaries.

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
    index, title = view._settings_sections[key]
    text = view._settings_toolbox.itemText(index)
    assert view._settings_toolbox.itemToolTip(index) == text
    return text.removeprefix(f"{title} — ") if text != title else ""


def _show_section(view: AlbumSettingsWidget, key: str) -> None:
    view._settings_toolbox.setCurrentIndex(view._settings_sections[key][0])


def test_page_format_summary_tracks_custom_format_and_page_changes(view, app):
    """Format and orientation changes bypass the generic settings signal."""
    _show_section(view, "format")

    view._page_format_combo.setCurrentIndex(view._page_format_combo.findData("custom"))
    view._custom_width_spin.setValue(345.5)
    view._custom_height_spin.setValue(123.25)
    # The summary describes the applied format, not values being edited.
    assert "210 × 297 mm" in _summary(view, "format")
    view._custom_apply_button.click()
    app.processEvents()
    _show_section(view, "covers")
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


def test_format_title_and_square_summary_never_show_orientation(view, app):
    assert view._settings_toolbox.itemText(0).startswith("Format — ")
    # The full label can remain inside the expanded form.
    assert view._page_format_combo.count() > 0
    _show_section(view, "format")
    view._page_format_combo.setCurrentIndex(view._page_format_combo.findData("custom"))
    view._custom_width_spin.setValue(180)
    view._custom_height_spin.setValue(180)
    view._custom_apply_button.click()
    _show_section(view, "covers")
    app.processEvents()
    assert _summary(view, "format") == "Personnalisé — 180 × 180 mm · Carré"
    assert "Portrait" not in _summary(view, "format")
    assert "Paysage" not in _summary(view, "format")

    _show_section(view, "format")
    view._custom_height_spin.setValue(181)
    view._custom_apply_button.click()
    _show_section(view, "covers")
    assert "Carré" not in _summary(view, "format")
    assert "Portrait" in _summary(view, "format")


def test_covers_do_not_show_partial_model_names(view):
    _show_section(view, "format")
    assert _summary(view, "covers") == ""
    # The four selectors remain available on the native Covers page.
    _show_section(view, "covers")
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
    _show_section(view, "format")
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
    sections = view._settings_sections
    assert len(sections) == 7
    assert "numbering_printing" in sections
    assert "numbers" not in sections and "printing" not in sections
    index = sections["numbering_printing"][0]
    assert view._settings_toolbox.itemText(index) == "Numérotation"

    view._page_numbers_checkbox.setChecked(False)
    view._page_multiple_4_checkbox.setChecked(True)
    _show_section(view, "format")
    assert _summary(view, "numbering_printing") == ""
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
        assert view._settings_toolbox.itemText(0).startswith("Format — ")
        view._add_special_page(view._front_matter_list, view._front_matter_combo)
        assert _summary(view, "front") == "1 page configured"
        index = view._settings_sections["numbering_printing"][0]
        assert view._settings_toolbox.itemText(index) == "Page numbering"
        assert _summary(view, "numbering_printing") == ""
        view._page_format_combo.setCurrentIndex(view._page_format_combo.findData("custom"))
        view._custom_width_spin.setValue(180)
        view._custom_height_spin.setValue(180)
        view._custom_apply_button.click()
        _show_section(view, "covers")
        assert _summary(view, "format") == "Custom — 180 × 180 mm · Square"
    finally:
        view.close()
