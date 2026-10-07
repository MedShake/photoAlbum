from PySide6.QtCore import QObject, QRunnable, Signal

from photoalbum.cache_manager import CacheManager


class _Signals(QObject):
    finished = Signal(object, object)


class LegacyCacheCleanupWorker(QRunnable):
    """Remove one project's old cache without accessing its database or UI."""

    def __init__(self, project_path):
        super().__init__()
        self.project_path = project_path
        self.signals = _Signals()

    def run(self):
        result = None
        try:
            if CacheManager().purge_legacy_cache_for_project(self.project_path):
                result = ("removed", None)
        except OSError as exc:
            result = ("failed", str(exc))
        self.signals.finished.emit(self.project_path, result)
