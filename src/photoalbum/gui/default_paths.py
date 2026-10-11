"""Cross-platform default locations for project and PDF save dialogs."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from photoalbum.app_info import APPLICATION_NAME


def _settings() -> QSettings:
    return QSettings("PhotoAlbum", APPLICATION_NAME)


def documents_or_home() -> Path:
    """Use the OS Documents folder when present; otherwise the user's home."""
    path = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    if path and Path(path).is_dir():
        return Path(path)
    return Path.home()


def project_directory() -> Path:
    """Start from the last successfully used project directory if accessible."""
    value = _settings().value("paths/last_project_directory", "")
    if value and Path(str(value)).is_dir():
        return Path(str(value))
    return documents_or_home()


def remember_project_directory(path: Path) -> None:
    _settings().setValue("paths/last_project_directory", str(path.parent))


def _pdf_directory_key(project: Path) -> str:
    # A stable settings key (project paths contain slashes and may be renamed).
    digest = sha256(str(project.resolve()).encode("utf-8")).hexdigest()
    return f"paths/last_pdf_export_directory/{digest}"


def pdf_destination(project: Path | None) -> Path:
    """Propose a PDF next to the project or in its last export directory."""
    if project is None:
        return documents_or_home() / "album.pdf"
    value = _settings().value(_pdf_directory_key(project), "")
    if value and Path(str(value)).is_dir():
        folder = Path(str(value))
    else:
        folder = project.parent
    return folder / f"{project.stem}.pdf"


def remember_pdf_directory(project: Path | None, output: Path) -> None:
    if project is not None:
        _settings().setValue(_pdf_directory_key(project), str(output.parent))
