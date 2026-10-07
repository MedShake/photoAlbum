"""Application-wide disk cache policy; asset fetching belongs to sources."""
from contextlib import contextmanager
from hashlib import sha256
import math
import os
from pathlib import Path
import shutil
from uuid import UUID, uuid4

from PySide6.QtCore import QLockFile, QSettings, QStandardPaths

from photoalbum.app_info import APPLICATION_NAME


GB = 1_000_000_000


class CacheManager:
    def __init__(self, root=None, settings=None):
        self.root = Path(root) if root is not None else (
            Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericCacheLocation))
            / "photoalbum"
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings = settings if settings is not None else QSettings("PhotoAlbum", APPLICATION_NAME)

    @property
    def quota_gb(self):
        try:
            value = float(self.settings.value("cache/quota_gb", 20))
            return value if math.isfinite(value) and value > 0 else 20.0
        except (TypeError, ValueError):
            return 20.0

    @property
    def unlimited(self):
        return self.settings.value("cache/unlimited", False, type=bool)

    def configure(self, quota_gb, unlimited):
        if not math.isfinite(quota_gb) or quota_gb <= 0:
            raise ValueError("Cache quota must be positive and finite")
        with self._guard():
            if self._leases():
                raise OSError("Cache is in use")
            self.settings.setValue("cache/quota_gb", quota_gb)
            self.settings.setValue("cache/unlimited", bool(unlimited))
            self.settings.sync()
            if self.settings.status() != QSettings.Status.NoError:
                raise OSError("Cannot save cache preferences")
        self.enforce_quota()

    def project_directory(self, project_id):
        return self.root / "projects" / UUID(project_id).hex

    def source_directory(self, project_id, source_id):
        return self.project_directory(project_id) / "sources" / sha256(source_id.encode()).hexdigest()

    def _files(self, directory=None):
        directory = directory or self.root / "projects"
        # Never follow a link out of the cache, including intermediate directories.
        if directory.is_symlink() or not directory.exists():
            return []
        files = []
        for current, dirs, names in os.walk(directory, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(current) / d).is_symlink()]
            files.extend(Path(current) / name for name in names if not (Path(current) / name).is_symlink())
        return files

    def used_bytes(self):
        total = 0
        for path in self._files():
            try:
                total += path.stat().st_size
            except FileNotFoundError:
                pass
        return total

    def available_bytes(self):
        return shutil.disk_usage(self.root).free

    @staticmethod
    def _is_link_like(path):
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        return bool(is_junction and is_junction())

    @staticmethod
    def _is_legacy_cache_name(name):
        return (
            name.startswith(".")
            and name.endswith(".photoalbum.cache")
            and len(name) > len("..photoalbum.cache")
        )

    @classmethod
    def _looks_like_legacy_cache(cls, path):
        return (
            cls._is_legacy_cache_name(path.name)
            and not cls._is_link_like(path)
            and (path / "assets").is_dir()
        )

    @staticmethod
    def _legacy_search_root(search_root=None):
        if search_root is not None:
            return Path(search_root).expanduser()
        home = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
        return Path(home) if home else Path.home()

    def legacy_cache_directories(self, search_root=None):
        """Find adjacent-cache directories created by pre-global-cache versions.

        The search is deliberately limited to the user's home directory by
        default. Symlinks/junctions are never followed and the current global
        cache is excluded.
        """
        search_root = self._legacy_search_root(search_root)
        if not search_root.is_dir() or self._is_link_like(search_root):
            return []

        cache_root = self.root.expanduser().resolve(strict=False)
        matches = []

        def ignore_error(_error):
            return None

        for current, dirs, _names in os.walk(
            search_root, topdown=True, followlinks=False, onerror=ignore_error,
        ):
            current_path = Path(current)
            kept = []
            for name in dirs:
                candidate = current_path / name
                try:
                    if self._is_link_like(candidate):
                        continue
                    if candidate.resolve(strict=False) == cache_root:
                        continue
                except OSError:
                    continue
                if self._looks_like_legacy_cache(candidate):
                    matches.append(candidate)
                    continue
                kept.append(name)
            dirs[:] = kept
        return matches

    def paths_size(self, paths):
        total = 0
        for directory in paths:
            for path in self._files(Path(directory)):
                try:
                    total += path.stat().st_size
                except (FileNotFoundError, OSError):
                    pass
        return total

    def purge_legacy_caches(self, paths, *, search_root=None):
        """Remove explicitly discovered legacy caches and return failures.

        Callers should pass paths returned by :meth:`legacy_cache_directories`.
        Names, link-like paths and containment in the searched user directory
        are checked again immediately before removal.
        """
        allowed_root = self._legacy_search_root(search_root).resolve(strict=False)
        failures = []
        for value in paths:
            path = Path(value)
            try:
                resolved = path.resolve(strict=False)
                if (
                    not resolved.is_relative_to(allowed_root)
                    or not self._looks_like_legacy_cache(path)
                ):
                    failures.append(path)
                    continue
                if path.exists():
                    shutil.rmtree(path)
            except OSError:
                failures.append(path)
        return failures

    @contextmanager
    def _guard(self):
        lock = QLockFile(str(self.root / ".maintenance.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(5000):
            raise OSError("Cache maintenance is busy")
        try:
            yield
        finally:
            lock.unlock()

    def _leases(self):
        scopes = set()
        for path in (self.root / "leases").glob("*.lock"):
            probe = QLockFile(str(path))
            probe.setStaleLockTime(0)
            if probe.tryLock(0):
                probe.unlock()  # Also removes leases left by a dead process.
            else:
                scopes.add(path.name.split(".")[0])
        return scopes

    @contextmanager
    def protect(self, project_id=None, *, light_only=False, trim=True):
        """Lease files across threads/processes; quota may temporarily be exceeded.

        An open project protects its lightweight assets. Export/import protects
        all assets until its consumer is finished, not just until download ends.
        """
        scope = "all" if project_id is None else UUID(project_id).hex + ("-light" if light_only else "-all")
        with self._guard():
            leases = self.root / "leases"
            leases.mkdir(exist_ok=True)
            lease = QLockFile(str(leases / f"{scope}.{uuid4().hex}.lock"))
            lease.setStaleLockTime(0)
            if not lease.tryLock(0):
                raise OSError("Cannot protect cached assets")
        try:
            yield
        finally:
            with self._guard():
                lease.unlock()
            if trim:
                self.enforce_quota()

    @staticmethod
    def touch(path):
        try:
            os.utime(path, None)
        except OSError:
            pass

    def enforce_quota(self, *, exclude=()):
        # Automatic maintenance must not turn a successful download/export into
        # a failure (e.g. a file is temporarily locked by the OS).
        try:
            self._enforce_quota(exclude=exclude)
        except OSError:
            pass

    def _enforce_quota(self, *, exclude=()):
        with self._guard():
            scopes = self._leases()
            self._finish_source_purges(scopes)
            if self.unlimited:
                return
            if "all" in scopes:
                return
            entries = []
            total = 0
            for path in self._files():
                try:
                    stat = path.stat()
                except FileNotFoundError:
                    continue
                total += stat.st_size
                relative = path.relative_to(self.root / "projects")
                project_id = relative.parts[0]
                heavy = "original" in relative.parts
                if (path in exclude or project_id + "-all" in scopes
                        or (not heavy and project_id + "-light" in scopes)):
                    continue
                entries.append((not heavy, stat.st_mtime_ns, path, stat.st_size))
            for _, _, path, size in sorted(entries):
                if total <= self.quota_gb * GB:
                    break
                try:
                    path.unlink()
                except OSError:
                    continue
                total -= size
            self._remove_empty_directories()

    def _finish_source_purges(self, scopes):
        markers = list((self.root / "pending-purges").glob("*"))
        if not markers:
            return
        for marker in markers:
            project, source_hash = marker.name.split(".", 1)
            if "all" in scopes or project + "-all" in scopes:
                continue
            directory = self.project_directory(project) / "sources" / source_hash
            for path in self._files():
                if path.is_relative_to(directory):
                    path.unlink(missing_ok=True)
            marker.unlink(missing_ok=True)
        self._remove_empty_directories()

    def _remove_empty_directories(self):
        for current, _, _ in os.walk(self.root / "projects", topdown=False, followlinks=False):
            try:
                Path(current).rmdir()
            except OSError:
                pass

    def purge(self, project_id=None, source_id=None):
        """Delete cache files only; source deletion may release its light assets."""
        with self._guard():
            scopes = self._leases()
            project = UUID(project_id).hex if project_id else None
            if source_id is not None and ("all" in scopes or project + "-all" in scopes):
                # Logical deletion has already succeeded. Finish physical removal
                # when an export/external-viewer lease no longer needs the files.
                pending = self.root / "pending-purges"
                pending.mkdir(exist_ok=True)
                (pending / f"{project}.{sha256(source_id.encode()).hexdigest()}").touch()
                return
            if ("all" in scopes or (project is None and scopes)
                    or (project and project + "-all" in scopes)
                    or (project and source_id is None and project + "-light" in scopes)):
                raise OSError("Cache is in use")
            directory = (self.source_directory(project, source_id) if source_id is not None
                         else self.project_directory(project) if project else self.root / "projects")
            for path in self._files():
                if path.is_relative_to(directory):
                    path.unlink(missing_ok=True)
            self._remove_empty_directories()
