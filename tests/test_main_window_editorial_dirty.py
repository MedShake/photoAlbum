from unittest.mock import Mock

from photoalbum.gui.main_window import MainWindow


class _WindowStub:
    _mark_editorial_album_dirty = (
        MainWindow._mark_editorial_album_dirty
    )
    _flush_editorial_album_changes = (
        MainWindow._flush_editorial_album_changes
    )
    _main_tab_changed = MainWindow._main_tab_changed


def _window_stub():
    window = _WindowStub()

    window._editorial_album_dirty = False
    window._previous_tab_index = 1
    window._photos_places_index = 1

    window._project_service = Mock()
    window._project_service.is_open = True

    window._preview_render_service = Mock()
    window._refresh_album_plan = Mock()
    window._update_pdf_summary = Mock()

    return window


def test_editorial_change_marks_album_dirty_without_refresh():
    window = _window_stub()

    window._mark_editorial_album_dirty()

    assert window._editorial_album_dirty is True
    window._preview_render_service.clear.assert_not_called()
    window._refresh_album_plan.assert_not_called()
    window._update_pdf_summary.assert_not_called()


def test_leaving_places_tab_flushes_editorial_changes_once():
    window = _window_stub()
    window._mark_editorial_album_dirty()

    window._main_tab_changed(2)

    assert window._editorial_album_dirty is False
    assert window._previous_tab_index == 2

    window._preview_render_service.clear.assert_not_called()
    window._refresh_album_plan.assert_called_once_with()
    window._update_pdf_summary.assert_called_once_with()


def test_tab_change_without_new_editorial_change_does_not_refresh():
    window = _window_stub()
    window._mark_editorial_album_dirty()

    window._main_tab_changed(2)
    window._main_tab_changed(3)
    window._main_tab_changed(1)
    window._main_tab_changed(2)

    window._preview_render_service.clear.assert_not_called()
    window._refresh_album_plan.assert_called_once_with()
    window._update_pdf_summary.assert_called_once_with()


def test_staying_on_places_tab_does_not_flush():
    window = _window_stub()
    window._mark_editorial_album_dirty()

    window._main_tab_changed(1)

    assert window._editorial_album_dirty is True
    window._preview_render_service.clear.assert_not_called()
    window._refresh_album_plan.assert_not_called()
    window._update_pdf_summary.assert_not_called()


def test_open_project_clears_image_cache_before_loading_new_preview():
    from pathlib import Path
    from types import SimpleNamespace

    events = []
    window = SimpleNamespace(
        _preview_render_service=Mock(),
        _hover_photo_preview=Mock(),
        _project_service=Mock(),
        _album_preview_widget=Mock(),
        _load_project_settings=lambda: events.append("settings"),
        _load_project_photos=lambda: events.append("photos"),
        _update_project_state=Mock(),
        _photos_widget=Mock(),
        _scan_controller=Mock(),
        _show_error=Mock(),
    )
    window._album_preview_widget.clear.side_effect = lambda: events.append("clear")
    window._photos_widget.source_edit.text.return_value = ""
    MainWindow._open_project_path(window, Path("other.photoalbum"))
    assert events == ["clear", "settings", "photos"]
    window._hover_photo_preview.clear.assert_called_once_with()
    window._show_error.assert_not_called()


def test_failed_project_open_does_not_discard_current_image_cache():
    from pathlib import Path
    from types import SimpleNamespace

    window = SimpleNamespace(
        _preview_render_service=Mock(),
        _hover_photo_preview=Mock(),
        _project_service=Mock(),
        _album_preview_widget=Mock(),
        _show_error=Mock(),
    )
    window._project_service.open.side_effect = OSError("Cannot open project")
    MainWindow._open_project_path(window, Path("missing.photoalbum"))
    window._album_preview_widget.clear.assert_not_called()
    # ProjectService.open closes the previous project before attempting the
    # replacement, so its in-flight hover results must no longer be accepted.
    window._hover_photo_preview.clear.assert_called_once_with()
    window._show_error.assert_called_once()
