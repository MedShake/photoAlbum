from dataclasses import replace
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from photoalbum.app import ProjectService
from photoalbum.cache_manager import CacheManager, GB
from photoalbum.database import PhotoRepository
from photoalbum.database.source_repository import SourceRepository
from photoalbum.models import Photo
from photoalbum.sources import ProjectSource, SourceAssetCache, SourceReconnectRequiredError
from tests.test_photo_sources import FakeRemoteSource


def cached_file(manager, project, source, kind, name, size):
    path = manager.source_directory(project, source) / kind / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_default_free_quota_and_unlimited_persist():
    manager = CacheManager()
    assert manager.quota_gb == 20
    assert not manager.unlimited
    manager.configure(12.37, True)
    reloaded = CacheManager()
    assert reloaded.quota_gb == 12.37
    assert reloaded.unlimited


def test_global_quota_prefers_heavy_lru_and_honors_leases():
    manager = CacheManager()
    first, second = uuid4().hex, uuid4().hex
    light = cached_file(manager, first, "local", "thumbnail", "light", 6)
    old = cached_file(manager, first, "remote", "original", "old", 8)
    recent = cached_file(manager, second, "remote", "original", "recent", 8)
    os.utime(old, (1, 1))
    os.utime(recent, (2, 2))
    assert manager.used_bytes() == 22
    assert manager.available_bytes() > 0
    manager.settings.setValue("cache/quota_gb", 14 / GB)
    with manager.protect():
        CacheManager().enforce_quota()
        assert old.exists()
        with pytest.raises(OSError):
            CacheManager().purge()
    assert not old.exists()
    assert recent.exists() and light.exists()
    assert manager.used_bytes() == 14
    manager.configure(1 / GB, True)
    assert manager.used_bytes() == 14
    manager.configure(1 / GB, False)
    assert manager.used_bytes() == 0


def test_light_assets_of_open_project_are_protected():
    manager = CacheManager()
    project = uuid4().hex
    light = cached_file(manager, project, "local", "preview", "page", 10)
    manager.settings.setValue("cache/quota_gb", 1 / GB)
    with manager.protect(project, light_only=True):
        manager.enforce_quota()
        assert light.exists()
    assert not light.exists()


def test_source_purge_waits_for_in_use_original_even_without_quota():
    manager = CacheManager()
    manager.configure(20, True)
    project = uuid4().hex
    original = cached_file(manager, project, "remote", "original", "image", 8)
    with manager.protect(project):
        manager.purge(project, "remote")
        assert original.exists()
    assert not original.exists()


def test_global_purge_removes_only_cache(tmp_path):
    manager = CacheManager()
    for _ in range(2):
        cached_file(manager, uuid4().hex, "source", "thumbnail", "image", 4)
    original = tmp_path / "original.jpg"
    original.write_bytes(b"original")
    link = manager.root / "projects" / "external"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pass
    manager.purge()
    assert manager.used_bytes() == 0
    assert original.read_bytes() == b"original"


def test_legacy_cache_search_and_cleanup_is_limited_and_safe(tmp_path):
    manager = CacheManager()
    home = tmp_path / "home"
    home.mkdir()
    first = home / "Albums" / ".summer.photoalbum.cache"
    second = home / "Archive" / ".family.photoalbum.cache"
    normal = home / "Albums" / "project.photoalbum.cache"
    for directory in (first, second):
        assets = directory / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        (assets / "asset.jpg").write_bytes(b"x" * 7)
    normal.mkdir(parents=True, exist_ok=True)
    (normal / "assets").mkdir()
    (normal / "assets" / "asset.jpg").write_bytes(b"x" * 7)

    # A link that merely looks like a legacy cache must never be traversed/deleted.
    linked_target = tmp_path / "linked-target"
    linked_target.mkdir()
    linked = home / ".linked.photoalbum.cache"
    try:
        linked.symlink_to(linked_target, target_is_directory=True)
    except OSError:
        linked = None

    found = manager.legacy_cache_directories(home)
    assert set(found) == {first, second}
    assert manager.paths_size(found) == 14
    assert manager.purge_legacy_caches(found, search_root=home) == []
    assert not first.exists() and not second.exists()
    assert normal.exists()
    assert linked_target.exists()
    if linked is not None:
        assert linked.exists()

    outside = tmp_path / ".outside.photoalbum.cache"
    (outside / "assets").mkdir(parents=True)
    assert manager.purge_legacy_caches([outside], search_root=home) == [outside]
    assert outside.exists()


def test_open_project_removes_only_its_exact_adjacent_legacy_cache(tmp_path):
    project = tmp_path / "album.photoalbum"
    service = ProjectService()
    service.create(project)
    service.close()

    legacy = tmp_path / ".album.photoalbum.cache"
    (legacy / "assets").mkdir(parents=True)
    (legacy / "assets" / "asset.jpg").write_bytes(b"legacy")
    unrelated = tmp_path / ".other.photoalbum.cache"
    (unrelated / "assets").mkdir(parents=True)
    (unrelated / "assets" / "asset.jpg").write_bytes(b"keep")

    service.open(project)
    try:
        assert service.legacy_cache_cleanup_result == ("removed", None)
        assert not legacy.exists()
        assert unrelated.exists()
    finally:
        service.close()


def test_open_project_ignores_non_legacy_adjacent_directory(tmp_path):
    project = tmp_path / "album.photoalbum"
    service = ProjectService()
    service.create(project)
    service.close()

    lookalike = tmp_path / ".album.photoalbum.cache"
    lookalike.mkdir()
    (lookalike / "keep.txt").write_text("not a legacy asset cache")

    service.open(project)
    try:
        assert service.legacy_cache_cleanup_result is None
        assert lookalike.exists()
    finally:
        service.close()


def test_legacy_cache_search_does_not_descend_into_current_global_cache(tmp_path):
    home = tmp_path / "home"
    root = home / "current-cache"
    manager = CacheManager(root=root)
    fake_legacy = root / ".inside.photoalbum.cache"
    (fake_legacy / "assets").mkdir(parents=True)
    outside = home / ".outside.photoalbum.cache"
    (outside / "assets").mkdir(parents=True)

    assert manager.legacy_cache_directories(home) == [outside]


@pytest.mark.parametrize("kind", ["local", "synology-photos"])
def test_source_cache_deleted_only_after_logical_success(tmp_path, monkeypatch, kind):
    service = ProjectService()
    service.create(tmp_path / "project.photoalbum")
    try:
        source = ProjectSource(id="s", kind=kind, name="S", collection_id="c", collection_name="C")
        service.set_photo_source(source)
        cache = service._asset_cache
        path = cached_file(cache.manager, cache.project_id, source.id, "thumbnail", "image", 4)
        other = cached_file(cache.manager, cache.project_id, "other", "thumbnail", "image", 4)
        with monkeypatch.context() as patch:
            def fail(*args):
                raise RuntimeError("database failure")
            patch.setattr(SourceRepository, "delete", fail)
            with pytest.raises(RuntimeError):
                service.delete_source(source.id)
        assert path.exists()
        service.delete_source(source.id)
        assert not path.exists()
        assert other.exists()
    finally:
        service.close()


def test_cache_survives_project_move_and_evicted_original_requires_reconnection(tmp_path):
    service = ProjectService()
    project = tmp_path / "before.photoalbum"
    service.create(project)
    source = ProjectSource(id="remote", kind="synology-photos", name="S", collection_id="c", collection_name="C")
    service.set_photo_source(source)
    cache = service._asset_cache
    photo = Photo(path=None, filename="a.jpg", source_id=source.id, asset_id="a", content_hash="v1")
    provider = FakeRemoteSource([])
    thumbnail = cache.materialize(photo, provider, quality="thumbnail")
    original = cache.materialize(photo, provider, quality="original")
    photo.path = tmp_path / ".old.photoalbum.cache" / "image.jpg"
    PhotoRepository(service._database).save(photo)
    service.close()
    moved = tmp_path / "after.photoalbum"
    project.rename(moved)
    service.open(moved)
    try:
        loaded = service.list_photos()[0]
        assert loaded.path == thumbnail
        service.materialize_originals([loaded])
        assert loaded.path == original
        assert service._asset_cache.project_id == cache.project_id
        original.unlink()
        with pytest.raises(SourceReconnectRequiredError):
            service.materialize_originals([loaded])
        assert service.list_photos()[0].path == thumbnail
        service.attach_source_session(source.id, provider)
        service.materialize_originals([loaded])
        assert original.exists()
        assert cache.path_for(replace(photo, content_hash="v2"), "original") != original
    finally:
        service.close()


def test_pdf_keeps_original_until_render_and_restores_preview_path(tmp_path):
    from photoalbum.gui.workers.pdf_export_worker import PdfExportWorker

    service = ProjectService()
    service.create(tmp_path / "export.photoalbum")
    source = ProjectSource(id="remote", kind="synology-photos", name="S", collection_id="c", collection_name="C")
    provider = FakeRemoteSource([])
    service.set_photo_source(source, provider)
    cache = service._asset_cache
    photo = Photo(path=None, filename="a.jpg", source_id=source.id, asset_id="a")
    thumbnail = cache.materialize(photo, provider, quality="thumbnail")
    photo.path = thumbnail
    cache.manager.settings.setValue("cache/quota_gb", 1 / GB)
    rendered = []

    class Exporter:
        def export(self, **kwargs):
            CacheManager().enforce_quota()
            assert photo.path == cache.path_for(photo, "original")
            assert photo.path.read_bytes() == b"original:a"
            rendered.append(True)

    worker = PdfExportWorker(
        Exporter(), output_path=tmp_path / "out.pdf",
        result=SimpleNamespace(template_photos=[photo]), settings=None, photos=[photo],
        page_width_mm=210, page_height_mm=297, dpi=150, metadata=None, content=None,
        prepare_assets=service.materialize_originals,
    )
    errors = []
    worker.failed.connect(errors.append)
    try:
        worker.run()
        assert errors == []
        assert rendered == [True]
        assert photo.path == thumbnail and thumbnail.exists()
        assert not cache.path_for(photo, "original").exists()
    finally:
        service.close()


def test_failed_download_does_not_publish_partial_original(tmp_path):
    cache = SourceAssetCache(tmp_path / "failed.photoalbum")
    photo = Photo(path=None, filename="a.jpg", source_id="remote", asset_id="a")

    class Provider:
        def fetch_original(self, asset, destination):
            destination.write_bytes(b"partial")
            raise OSError("disconnected")

    with pytest.raises(OSError):
        cache.materialize(photo, Provider(), quality="original")
    assert cache.cached_path(photo, "original") is None
    assert cache.manager.used_bytes() == 0
