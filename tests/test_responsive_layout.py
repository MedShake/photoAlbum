"""GUI regression checks for small logical displays (Linux/Windows DPI).

Run with QT_QPA_PLATFORM=offscreen when no graphical session is available.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from photoalbum.gui.main_window import MainWindow, ResponsiveTabWidget
from photoalbum.gui.widgets.accordion_section import AccordionGroup, AccordionSection
from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.gui.widgets.pdf_export_widget import PdfExportWidget
from photoalbum.gui.widgets.source_card import SourceCard
from photoalbum.i18n import Translator
from photoalbum.sources import ProjectSource
from photoalbum.template_engine import create_template_registry


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_accordion_can_hide_real_body_without_losing_it(app):
    body = QWidget()
    body.setMinimumHeight(280)
    section = AccordionSection("Options", body)
    section.show()
    app.processEvents()
    assert not section.expanded
    assert body.isHidden()
    small_height = section.minimumSizeHint().height()

    section.set_expanded(True)
    app.processEvents()
    assert section.expanded
    assert not body.isHidden()
    assert section.minimumSizeHint().height() > small_height + 150

    section.set_expanded(False)
    app.processEvents()
    assert body.isHidden()
    section.close()


def test_accordion_group_keeps_multiple_sections_open_by_default(app):
    group = AccordionGroup()
    first = group.add("first", AccordionSection("First", QWidget()))
    second = group.add("second", AccordionSection("Second", QWidget()))
    first.set_expanded(True)
    second.set_expanded(True)
    assert first.expanded and second.expanded
    first.set_expanded(False)
    assert not first.expanded and second.expanded
    group.collapse_all()
    assert not any(section.expanded for section in group.sections.values())


def test_accordion_group_can_still_be_explicitly_exclusive(app):
    group = AccordionGroup(exclusive=True)
    first = group.add("first", AccordionSection("First", QWidget()))
    second = group.add("second", AccordionSection("Second", QWidget()))
    first.set_expanded(True)
    second.set_expanded(True)
    assert not first.expanded and second.expanded


def test_album_settings_has_compact_exclusive_accordions(app):
    view = AlbumSettingsWidget(create_template_registry(), Translator("fr"))
    view.resize(960, 450)
    view.show()
    app.processEvents()
    assert isinstance(view._settings_scroll, QScrollArea)
    assert len(view._accordions.sections) == 7
    assert "numbering_printing" in view._accordions.sections
    assert "numbers" not in view._accordions.sections
    assert "printing" not in view._accordions.sections
    assert [key for key, section in view._accordions.sections.items() if section.expanded] == ["format"]
    assert view.minimumSizeHint().height() < 450
    assert view._settings_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    # Opening a section collapses the previously expanded section.
    assert view._accordions.exclusive
    view._accordions.sections["covers"].set_expanded(True)
    app.processEvents()
    assert not view._accordions.sections["format"].expanded
    assert view._accordions.sections["covers"].expanded
    assert view._front_cover_combo.count() > 0
    view._accordions.sections["covers"].set_expanded(False)
    assert not view._accordions.sections["format"].expanded
    assert not view._accordions.sections["covers"].expanded
    # An accordion can always be reopened after everything is closed.
    view._accordions.sections["dividers"].set_expanded(True)
    assert view._accordions.sections["dividers"].expanded
    assert sum(section.expanded for section in view._accordions.sections.values()) == 1
    before = view.settings()
    view.set_settings(before)
    assert view.settings() == before
    view.close()


def test_pdf_has_pinned_destination_generate_and_compact_options(app):
    settings = AlbumSettingsWidget(create_template_registry(), Translator("fr"))
    view = PdfExportWidget(
        translator=Translator("fr"),
        project_service=SimpleNamespace(is_open=False),
        settings_provider=settings.settings,
        result_provider=lambda: None,
        before_export=lambda: None,
    )
    view.resize(960, 450)
    view.show()
    app.processEvents()
    assert len(view._pdf_accordions.sections) == 3
    assert "document" not in view._pdf_accordions.sections
    assert view._pdf_output_group.title().startswith("Fichier de sortie : A4")
    assert view._pdf_accordions.sections["content"].expanded
    assert not view._options_scroll.isAncestorOf(view._pdf_output_edit)
    assert not view._options_scroll.isAncestorOf(view.generate_button)
    assert view._options_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert view.minimumSizeHint().height() < 450
    assert view._pdf_accordions.exclusive
    view._pdf_accordions.sections["metadata"].set_expanded(True)
    assert not view._pdf_accordions.sections["content"].expanded
    assert view._pdf_accordions.sections["metadata"].expanded
    view._pdf_accordions.sections["metadata"].set_expanded(False)
    assert not view._pdf_accordions.sections["content"].expanded
    assert not view._pdf_accordions.sections["metadata"].expanded
    view._pdf_accordions.sections["quality"].set_expanded(True)
    assert sum(section.expanded for section in view._pdf_accordions.sections.values()) == 1
    view._pdf_title_edit.setText("Titre de test")
    view._update_option_summaries()
    assert "Titre de test" in view._pdf_accordions.sections["metadata"]._summary.text()
    view.close()
    settings.close()



def test_pdf_output_title_shows_live_format_pages_and_photo_count(app):
    settings = AlbumSettingsWidget(create_template_registry(), Translator("fr"))
    state = {"result": SimpleNamespace(total_page_count=595), "photos": range(1787)}
    view = PdfExportWidget(
        translator=Translator("fr"),
        project_service=SimpleNamespace(
            is_open=True,
            list_album_photos=lambda: state["photos"],
        ),
        settings_provider=settings.settings,
        result_provider=lambda: state["result"],
        before_export=lambda: None,
    )
    try:
        assert "document" not in view._pdf_accordions.sections
        title = view._pdf_output_group.title()
        assert "A4 — 210 × 297 mm" in title
        assert "595 pages" in title
        assert "1787 photos" in title

        state["result"] = SimpleNamespace(total_page_count=1)
        state["photos"] = range(1)
        view.update_summary()
        assert "1 page / 1 photo" in view._pdf_output_group.title()

        state["result"] = None
        state["photos"] = range(0)
        view.update_summary()
        assert "Calculé lors de la génération" in view._pdf_output_group.title()
        assert "0 photos" in view._pdf_output_group.title()
    finally:
        view.close()
        settings.close()

def test_source_card_actions_are_not_fixed_width_and_policies_remain(app):
    # Use the real domain object to detect accidental changes to signal wiring.
    source = ProjectSource(
        id="test-source", name="Images", kind="local", enabled=True,
        collection_id="images", collection_name="Images",
        config={"directory": "/tmp/pictures", "recursive": True},
    )
    card = SourceCard(source, {}, Translator("fr"))
    card.show()
    app.processEvents()
    assert card.sync_button.minimumWidth() < 112 or card.sync_button.maximumWidth() != 112
    assert len(card._combos) == 3
    assert card._nominatim is not None
    card.set_expanded(False)
    assert card.details_widget.isHidden()
    card.close()


def test_main_window_tabs_do_not_force_a_tall_minimum(app, tmp_path, monkeypatch):
    # Avoid reading/writing the developer's actual saved geometry.
    from PySide6.QtCore import QSettings
    import photoalbum.gui.main_window as main_window_module
    path = str(tmp_path / "test-window.ini")
    monkeypatch.setattr(
        main_window_module, "QSettings",
        lambda *_args: QSettings(path, QSettings.Format.IniFormat),
    )
    window = MainWindow(language="fr")
    try:
        assert isinstance(window._tabs, ResponsiveTabWidget)
        assert window._tabs.minimumSizeHint().height() <= 300
        assert window.minimumSizeHint().height() <= 540
        # Qt must accept a compact viewport even when the current tab changes.
        for index in (0, 2, 5):
            window._tabs.setCurrentIndex(index)
            window.resize(960, 540)
            app.processEvents()
            assert window.height() <= 540
    finally:
        window.close()
