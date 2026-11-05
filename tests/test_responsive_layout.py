"""GUI regression checks for small logical displays (Linux/Windows DPI).

Run with QT_QPA_PLATFORM=offscreen when no graphical session is available.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QToolBox

from photoalbum.gui.main_window import MainWindow, ResponsiveTabWidget
from photoalbum.gui.widgets.album_settings_widget import AlbumSettingsWidget
from photoalbum.gui.widgets.pdf_export_widget import PdfExportWidget
from photoalbum.gui.widgets.source_card import SourceCard
from photoalbum.i18n import Translator
from photoalbum.sources import ProjectSource
from photoalbum.template_engine import create_template_registry


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_album_settings_has_compact_native_pages(app):
    view = AlbumSettingsWidget(create_template_registry(), Translator("fr"))
    view.resize(960, 450)
    view.show()
    app.processEvents()
    toolbox = view._settings_toolbox
    assert type(toolbox) is QToolBox
    assert toolbox.count() == 7
    assert "numbering_printing" in view._settings_sections
    assert "numbers" not in view._settings_sections
    assert "printing" not in view._settings_sections
    assert toolbox.currentIndex() == view._settings_sections["format"][0]
    assert view.minimumSizeHint().height() < 450
    toolbox.setCurrentIndex(view._settings_sections["covers"][0])
    app.processEvents()
    assert not toolbox.widget(view._settings_sections["format"][0]).isVisibleTo(view)
    assert view._front_cover_combo.count() > 0
    before = view.settings()
    for index in range(toolbox.count()):
        toolbox.setCurrentIndex(index)
        app.processEvents()
        assert toolbox.widget(index).isVisibleTo(view)
        assert view.height() == 450
        assert view.settings() == before
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
    toolbox = view._options_container
    assert type(toolbox) is QToolBox
    assert toolbox.count() == 3
    assert "document" not in view._option_sections
    assert view._pdf_output_group.title().startswith("Fichier de sortie : A4")
    assert toolbox.currentIndex() == view._option_sections["content"][0]
    assert not toolbox.isAncestorOf(view._pdf_output_edit)
    assert not toolbox.isAncestorOf(view.generate_button)
    assert view.minimumSizeHint().height() < 450
    before = view.project_settings()
    for index in range(toolbox.count()):
        toolbox.setCurrentIndex(index)
        app.processEvents()
        assert toolbox.widget(index).isVisibleTo(view)
        assert view.height() == 450
        assert view.project_settings() == before
    view._pdf_title_edit.setText("Titre de test")
    view._update_option_summaries()
    assert "Titre de test" in toolbox.itemText(view._option_sections["metadata"][0])
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
        assert "document" not in view._option_sections
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
        window.show()
        app.processEvents()
        area = window.screen().availableGeometry()
        # Put half the frame beyond the screen regardless of its resolution.
        frame = window.frameGeometry()
        window.move(
            area.right() - frame.width() // 2,
            area.bottom() - frame.height() // 2,
        )
        app.processEvents()
        assert not area.contains(window.frameGeometry())
        window._fit_geometry_to_screen()
        assert area.contains(window.frameGeometry())
    finally:
        window.close()
