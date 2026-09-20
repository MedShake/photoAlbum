from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def _application_icon() -> QIcon:
    """Return the application icon bundled with the package."""
    icon_path = (
        Path(__file__).resolve().parent.parent
        / "resources"
        / "icons"
        / "photoalbum.svg"
    )
    return QIcon(str(icon_path))


def _system_language() -> str:
    """Return the supported language matching the system locale."""
    locale = QLocale.system()

    if locale.language() == QLocale.Language.French:
        return "fr"

    # English is both a supported language and the fallback for
    # every system language for which no translation exists yet.
    return "en"


def _install_qt_translation(application: QApplication, language: str) -> QTranslator | None:
    """Localize Qt-owned UI using catalogs supplied by the installed Qt runtime."""
    locale = QLocale(language)
    QLocale.setDefault(locale)
    if language == "en":
        # English is Qt's source language and needs no catalog.
        return None

    translator = QTranslator(application)
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(locale, "qtbase", "_", translations_path):
        application.installTranslator(translator)
        return translator

    logging.getLogger(__name__).warning(
        "Qt translation for %s could not be loaded from %s; Qt labels will use English.",
        language, translations_path,
    )
    return None


def _parse_arguments() -> argparse.Namespace:
    """Parse Photo Album GUI command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="photo-album",
        description="Photo Album graphical application.",
    )
    parser.add_argument(
        "-l",
        "--language",
        choices=("fr", "en"),
        default=None,
        help=(
            "force the application language; by default the system "
            "language is used, with English as fallback"
        ),
    )
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        help="Photo Album project to open",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_arguments()

    application = QApplication([sys.argv[0]])

    application.setApplicationName("Photo Album")
    application.setOrganizationName("Photo Album")
    application.setWindowIcon(_application_icon())

    language = (
        args.language
        if args.language is not None
        else _system_language()
    )

    # Keep the translator alive for the entire application event loop.
    qt_translator = _install_qt_translation(application, language)

    window = MainWindow(
        language=language
    )

    if args.project is not None:
        window._open_project_path(args.project)

    window.show()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
