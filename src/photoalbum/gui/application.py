from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QSettings, QTimer, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from photoalbum.app_info import (
    APPLICATION_NAME,
    ORGANIZATION_NAME,
)

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
        description=f"{APPLICATION_NAME} graphical application.",
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
        "--smoke-test",
        type=Path,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        help=f"{APPLICATION_NAME} project to open",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_arguments()

    if args.smoke_test is not None:
        # Release checks must not read or overwrite a user's desktop settings.
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                          str(args.smoke_test.parent / "settings"))

    application = QApplication([sys.argv[0]])

    application.setApplicationName(
        APPLICATION_NAME
    )
    application.setOrganizationName(
        ORGANIZATION_NAME
    )
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

    if args.smoke_test is not None:
        QTimer.singleShot(250, lambda: _complete_smoke_test(application, window, args.smoke_test))

    return application.exec()


def _complete_smoke_test(application: QApplication, window: MainWindow, report: Path) -> None:
    try:
        if not window.isVisible():
            raise RuntimeError("The main window is not visible")
        if not window.close():
            raise RuntimeError("The main window could not close")
        report.write_text("ok\n", encoding="utf-8")
    except Exception:
        logging.getLogger(__name__).exception("GUI startup check failed")
        application.exit(1)
    else:
        application.exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
