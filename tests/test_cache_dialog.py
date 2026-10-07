import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QGroupBox, QMessageBox

from photoalbum.cache_manager import CacheManager, GB
from photoalbum.gui.cache_dialog import CacheDialog
from photoalbum.gui.main_window import MainWindow
from photoalbum.i18n import Translator


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_dialog_free_quota_unlimited_warning_and_persistence(app, monkeypatch):
    manager = CacheManager()
    monkeypatch.setattr(manager, "available_bytes", lambda: GB)
    dialog = CacheDialog(Translator("fr"), manager=manager)
    assert dialog.quota_spin.value() == 20
    assert dialog.minimumWidth() >= 700
    assert dialog.minimumHeight() >= 360
    assert dialog.quota_spin.minimumWidth() >= 180
    groups = {group.title() for group in dialog.findChildren(QGroupBox)}
    assert {"Gestion de la taille du cache", "Nettoyage du cache"} <= groups
    assert dialog.quota_spin.isEnabled() and dialog.purge_button.isEnabled()
    assert dialog.warning_label.text()
    dialog.quota_spin.setValue(12.37)
    dialog.unlimited_checkbox.setChecked(True)
    assert not dialog.quota_spin.isEnabled()
    assert not dialog.warning_label.text()
    dialog.unlimited_checkbox.setChecked(False)
    assert dialog.quota_spin.isEnabled()
    assert dialog.warning_label.text()
    dialog.save_button.click()  # Insufficient free space warns, but does not block.
    assert CacheManager().quota_gb == 12.37
    second = CacheDialog(Translator("en"), manager=CacheManager())
    second.unlimited_checkbox.setChecked(True)
    second.save_button.click()
    assert CacheManager().unlimited
    dialog.deleteLater()
    second.deleteLater()


def test_purge_needs_confirmation_and_rechecks_project_state(app, monkeypatch):
    manager = CacheManager()
    calls = []
    legacy = manager.root.parent / ".legacy.photoalbum.cache"
    legacy.mkdir()
    (legacy / "image.jpg").write_bytes(b"legacy")
    legacy_searches = []
    monkeypatch.setattr(
        manager, "legacy_cache_directories",
        lambda: legacy_searches.append(True) or [legacy],
    )
    monkeypatch.setattr(manager, "purge", lambda: calls.append("current"))
    monkeypatch.setattr(manager, "purge_legacy_caches", lambda paths: calls.append(tuple(paths)) or [])
    active = [False]
    dialog = CacheDialog(Translator("fr"), project_is_open=lambda: active[0], manager=manager)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    assert not dialog.legacy_cleanup_checkbox.isChecked()
    dialog.purge_button.click()
    assert calls == []
    assert legacy_searches == []
    asked = []
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args: asked.append(args[2]) or QMessageBox.StandardButton.Yes,
    )
    dialog.legacy_cleanup_checkbox.setChecked(True)
    dialog.purge_button.click()
    assert calls == ["current", (legacy,)]
    assert legacy_searches == [True]
    assert "1" in asked[0]
    assert "ancien" in asked[0].lower()
    active[0] = True
    dialog._purge()
    assert calls == ["current", (legacy,)]
    dialog.deleteLater()


@pytest.mark.parametrize("language", ["fr", "en"])
def test_menu_opens_readonly_dialog_with_project_and_editable_without(app, tmp_path, monkeypatch, language):
    window = MainWindow(language=language)
    tr = Translator(language).tr
    seen = []

    def inspect(dialog):
        active = window._project_service.is_open
        seen.append(active)
        assert dialog.quota_spin.isEnabled() == (not active)
        assert dialog.unlimited_checkbox.isEnabled() == (not active)
        assert dialog.purge_button.isEnabled() == (not active)
        assert dialog.legacy_cleanup_checkbox.isEnabled() == (not active)
        assert dialog.save_button.isEnabled() == (not active)
        assert dialog.project_label.isHidden() == (not active)
        assert dialog.project_label.text() == tr("cache.close_project")
        return 0

    monkeypatch.setattr(CacheDialog, "exec", inspect)
    try:
        actions = window.menuBar().actions()
        assert actions[0].text() == tr("main.file")
        assert actions[1].text() == tr("main.settings")
        assert window._cache_action in actions[1].menu().actions()
        window._cache_action.trigger()
        window._project_service.create(tmp_path / "open.photoalbum")
        window._set_scan_running(True)
        assert window._cache_action.isEnabled()
        window._cache_action.trigger()
        assert seen == [False, True]
    finally:
        window._project_service.close()
        window.deleteLater()
