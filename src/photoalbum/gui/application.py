from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def _system_language() -> str:
    """Return the supported language matching the system locale."""
    locale = QLocale.system()

    if locale.language() == QLocale.Language.French:
        return "fr"

    # English is both a supported language and the fallback for
    # every system language for which no translation exists yet.
    return "en"


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

    return parser.parse_args()


def main() -> int:
    args = _parse_arguments()

    application = QApplication([sys.argv[0]])

    application.setApplicationName("Photo Album")
    application.setOrganizationName("Photo Album")

    language = (
        args.language
        if args.language is not None
        else _system_language()
    )

    window = MainWindow(
        language=language
    )
    window.show()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())