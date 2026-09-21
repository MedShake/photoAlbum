from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from photoalbum.gui.preview_image_cache import PreviewImageCache


def cache():
    app = QApplication.instance() or QApplication([])
    result = PreviewImageCache()
    result._pool = SimpleNamespace(start=Mock())
    return result


def finish(service, token):
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(0xff123456)
    service._finished(token, image)


def test_paint_never_decodes_and_resize_reuses_one_image():
    service = cache()
    for size in (100, 200, 500):
        assert service.load("a.jpg", QSize(size, size)).isNull()
    service._pool.start.assert_not_called()
    service.prioritize(["a.jpg", "a.jpg"])
    service.prioritize(["a.jpg"])
    assert service._pool.start.call_count == 1
    finish(service, next(iter(service._active)))
    first = service.load("a.jpg", QSize(100, 100))
    assert not first.isNull()
    assert service.load("a.jpg", QSize(500, 500)) is first
    service.prioritize(["a.jpg"])
    assert service._pool.start.call_count == 1


def test_viewport_replaces_queue_and_limits_concurrency():
    service = cache()
    service.prioritize(["a", "b", "c", "d"])
    assert service._pool.start.call_count == 2
    service.prioritize(["z", "y"])
    finish(service, next(iter(service._active)))
    assert service._pool.start.call_args.args[0].path == "z"
    assert len(service._active) == 2
    assert "c" not in service._queue


def test_clear_discards_old_project_results():
    service = cache()
    service.prioritize(["a"])
    token = next(iter(service._active))
    service.clear()
    finish(service, token)
    assert service.load("a", QSize(10, 10)).isNull()


def test_higher_density_upgrades_and_lower_density_reuses():
    service = cache()
    service.set_resolution(550, 778, 1)
    service.prioritize(["a"])
    finish(service, next(iter(service._active)))
    first = service.load("a", QSize(10, 10))
    service.set_resolution(550, 778, 2)
    service.prioritize(["a"])
    assert service.load("a", QSize(10, 10)) is first
    assert service._pool.start.call_args.args[0].edge == 1556
    finish(service, next(iter(service._active)))
    service.set_resolution(550, 778, 1)
    service.prioritize(["a"])
    assert service._pool.start.call_count == 2
    assert len(service._cache) == 1


def test_real_decode_runs_off_gui_thread_and_applies_exif(tmp_path, monkeypatch):
    import time
    from PIL import Image
    from PySide6.QtCore import QThread
    from photoalbum.gui import preview_image_cache

    app = QApplication.instance() or QApplication([])
    path = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (80, 40), "red").save(path, exif=exif)
    threads = []
    original_reader = preview_image_cache.QImageReader

    def reader(source):
        threads.append(QThread.currentThread() == app.thread())
        return original_reader(source)

    monkeypatch.setattr(preview_image_cache, "QImageReader", reader)
    service = PreviewImageCache()
    finished_on_gui = []
    service.ready.connect(lambda path: finished_on_gui.append(QThread.currentThread() == app.thread()))
    service.prioritize([path])
    deadline = time.monotonic() + 3
    while service._active:
        app.processEvents()
        assert time.monotonic() < deadline
        time.sleep(0.001)
    pixmap = service.load(path, QSize(40, 40))
    assert pixmap.height() > pixmap.width()
    assert threads == [False]
    assert finished_on_gui == [True]


def test_changed_source_rejects_running_result(tmp_path):
    service = cache()
    path = tmp_path / "new.jpg"
    service.prioritize([path])
    token = next(iter(service._active))
    path.write_bytes(b"changed")
    service.invalidate_changed_sources()
    finish(service, token)
    assert service.load(path, QSize(10, 10)).isNull()
