"""Shared GUI setup and isolation from the user's real application cache."""
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest

from photoalbum.cache_manager import CacheManager


@pytest.fixture
def show_active_window():
    """Wait for the window manager before testing focus or window shortcuts."""
    def show(widget):
        widget.show()
        assert QTest.qWaitForWindowExposed(widget, 3000)
        widget.activateWindow()
        assert QTest.qWaitForWindowActive(widget, 3000)

    return show


@pytest.fixture(autouse=True)
def isolated_application_cache(tmp_path, monkeypatch):
    original = CacheManager.__init__

    def initialize(self, root=None, settings=None):
        original(
            self,
            root if root is not None else tmp_path / "application-cache",
            settings if settings is not None else QSettings(
                str(tmp_path / "cache-preferences.ini"), QSettings.Format.IniFormat
            ),
        )

    monkeypatch.setattr(CacheManager, "__init__", initialize)
