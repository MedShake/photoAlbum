"""Keep cache tests and provider fixtures away from the user's real cache."""
import pytest
from PySide6.QtCore import QSettings

from photoalbum.cache_manager import CacheManager


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
