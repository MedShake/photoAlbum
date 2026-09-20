import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox

from photoalbum.gui.application import _install_qt_translation


@pytest.mark.parametrize("language, expected", [
    ("fr", ["Annuler", "Appliquer", "Fermer"]),
    ("en", ["Cancel", "Apply", "Close"]),
])
def test_standard_qt_buttons_follow_application_language(language, expected, tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    previous_locale = QLocale()
    translator = None
    box = message = None
    monkeypatch.chdir(tmp_path)
    try:
        # Deliberately start with the opposite locale; do not depend on the OS.
        QLocale.setDefault(QLocale("en" if language == "fr" else "fr"))
        translator = _install_qt_translation(app, language)
        assert (translator is not None) == (language == "fr")
        assert QLocale().language() == QLocale(language).language()
        buttons = QDialogButtonBox.StandardButton
        box = QDialogButtonBox(buttons.Cancel | buttons.Apply | buttons.Close)
        assert [box.button(button).text().replace("&", "") for button in (
            buttons.Cancel, buttons.Apply, buttons.Close,
        )] == expected
        message = QMessageBox()
        message.setStandardButtons(QMessageBox.StandardButton.Cancel)
        assert message.button(QMessageBox.StandardButton.Cancel).text().replace("&", "") == expected[0]
    finally:
        for widget in (box, message):
            if widget is not None:
                widget.close()
                widget.deleteLater()
        if translator is not None:
            app.removeTranslator(translator)
            translator.deleteLater()
        QLocale.setDefault(previous_locale)
