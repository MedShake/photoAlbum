"""Regression checks for secondary dialogs on compact desktop work areas."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QTableWidget,
    QTextBrowser,
)

from photoalbum.album import PageInstance
from photoalbum.gui import dialog_geometry
from photoalbum.gui.cache_dialog import CacheDialog
from photoalbum.gui.help_dialog import HelpDialog
from photoalbum.gui.page_instance_dialog import PageInstanceDialog
from photoalbum.gui.template_pack_help_dialog import TemplatePackHelpDialog
from photoalbum.gui.widgets.photo_places_widget import PhotoPlacesWidget
from photoalbum.i18n import Translator
from photoalbum.models import Photo
from photoalbum.templates.msb.theme import MsbTheme
from photoalbum.templates.msb.theme_dialog import MsbThemeDialog
from photoalbum.template_engine import register_discovered_template_extensions


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(params=[QRect(0, 0, 1024, 540), QRect(0, 0, 800, 540)])
def compact_work_area(monkeypatch, request):
    """1024x600 display with taskbar; also an 800-wide fallback display."""
    area = request.param
    monkeypatch.setattr(dialog_geometry, "_available_geometry", lambda _dialog: area)
    return area


def _assert_fits_work_area(dialog: QDialog, area: QRect) -> None:
    # Qt sizes are logical pixels. The tested area already excludes taskbars.
    assert dialog.width() <= area.width()
    assert dialog.height() <= area.height()
    assert dialog.width() >= dialog.minimumWidth()
    assert dialog.height() >= dialog.minimumHeight()


def test_dialog_sizing_preserves_large_screen_preferred_sizes(app, monkeypatch):
    monkeypatch.setattr(
        dialog_geometry,
        "_available_geometry",
        lambda _dialog: QRect(0, 0, 1920, 1040),
    )
    for dialog_type, preferred in (
        (HelpDialog, (760, 680)),
        (TemplatePackHelpDialog, (1000, 720)),
    ):
        dialog = dialog_type(Translator("fr"))
        try:
            assert (dialog.width(), dialog.height()) == preferred
        finally:
            dialog.close()


def test_help_and_template_documentation_fit_compact_screen(app, compact_work_area):
    for dialog_type in (HelpDialog, TemplatePackHelpDialog):
        dialog = dialog_type(Translator("fr"))
        try:
            _assert_fits_work_area(dialog, compact_work_area)
            assert dialog.findChild(QDialogButtonBox) is not None
            if dialog_type is HelpDialog:
                assert dialog.findChild(QTextBrowser) is not None
        finally:
            dialog.close()


def test_batch_places_dialog_fits_compact_screen(
    app, compact_work_area, monkeypatch, tmp_path
):
    widget = PhotoPlacesWidget()
    photo = Photo(path=tmp_path / "example.jpg", filename="example.jpg")
    monkeypatch.setattr(widget, "_group_location_candidates", lambda *args: [photo])
    checkbox = QCheckBox()
    checkbox.setProperty("location_key", "city")
    checkbox.setProperty("location_value", "Paris")
    seen = []

    def inspect(dialog):
        _assert_fits_work_area(dialog, compact_work_area)
        assert dialog.findChild(QDialogButtonBox) is not None
        assert dialog.findChild(QTableWidget) is not None
        seen.append(True)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect)
    try:
        widget._open_group_location_dialog(photo, checkbox)
        assert seen == [True]
    finally:
        widget.close()


def test_other_secondary_dialogs_keep_reasonable_minimum_sizes(app):
    """Guard their compact layouts without changing or constraining behaviour."""
    cache = CacheDialog(Translator("fr"))
    theme = MsbThemeDialog(MsbTheme(), translator=Translator("fr"))
    try:
        for dialog in (cache, theme):
            assert dialog.minimumWidth() <= 1024
            assert dialog.minimumHeight() <= 540
            assert dialog.findChild(QDialogButtonBox) is not None
    finally:
        cache.close()
        theme.close()


def test_template_settings_dialog_keeps_footer_and_scrollable_controls(app):
    """The template editor already has screen-aware sizing and scrolling."""
    from PySide6.QtWidgets import QScrollArea

    register_discovered_template_extensions()
    dialog = PageInstanceDialog(
        PageInstance(template_id="photo-page-1"),
        [],
        translator=Translator("en"),
    )
    try:
        assert dialog.findChild(QScrollArea) is not None
        assert dialog.height() <= dialog.screen().availableGeometry().height()
    finally:
        dialog.close()
