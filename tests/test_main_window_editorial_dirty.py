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

    window._preview_render_service.clear.assert_called_once_with()
    window._refresh_album_plan.assert_called_once_with()
    window._update_pdf_summary.assert_called_once_with()


def test_tab_change_without_new_editorial_change_does_not_refresh():
    window = _window_stub()
    window._mark_editorial_album_dirty()

    window._main_tab_changed(2)
    window._main_tab_changed(3)
    window._main_tab_changed(1)
    window._main_tab_changed(2)

    window._preview_render_service.clear.assert_called_once_with()
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
