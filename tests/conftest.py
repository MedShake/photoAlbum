"""Shared GUI setup and isolation from the user's real application cache."""
import gc
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, QThreadPool
from PySide6.QtGui import QPixmapCache
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from shiboken6 import delete, isValid

from photoalbum.cache_manager import CacheManager


def _dispose_widgets(application):
    # close() only hides most widgets. Destroy them while QApplication and its
    # current style still exist, rather than during Python's finalization or a
    # later test's setStyle(). Workers must finish before their GUI owners die.
    assert QThreadPool.globalInstance().waitForDone(10000), "Qt workers did not finish"
    for widget in application.topLevelWidgets():
        if isValid(widget):
            widget.hide()
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    # Some modules create Qt objects at collection time. Adopt that same
    # application and keep a strong reference throughout the entire session.
    application = QApplication.instance() or QApplication([])
    yield application
    _dispose_widgets(application)
    from photoalbum.gui.icon_resources import resource_icon
    resource_icon.cache_clear()
    QPixmapCache.clear()
    delete(application)


@pytest.fixture(autouse=True)
def dispose_test_widgets(qt_application, isolated_application_cache):
    yield
    _dispose_widgets(qt_application)


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
def isolated_application_cache(tmp_path_factory, monkeypatch):
    original = CacheManager.__init__
    # Avoid appending long test names to already deeply nested asset paths.
    # With --basetemp C:\pat this gives e.g. C:\pat\c0\a on Windows.
    directory = Path(tmp_path_factory.mktemp("c"))

    def initialize(self, root=None, settings=None):
        original(
            self,
            root if root is not None else directory / "a",
            settings if settings is not None else QSettings(
                str(directory / "p.ini"), QSettings.Format.IniFormat
            ),
        )

    monkeypatch.setattr(CacheManager, "__init__", initialize)
