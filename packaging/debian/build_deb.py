"""Build a Debian package from the PyInstaller Linux bundle."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "packaging" / "pyinstaller" / "dist" / "photo-album"
ICON = ROOT / "src" / "photoalbum" / "resources" / "icons" / "photoalbum.svg"
DESKTOP = ROOT / "packaging" / "debian" / "photo-album.desktop"

PYPROJECT = ROOT / "pyproject.toml"


def project_version() -> str:
    import tomllib

    with PYPROJECT.open("rb") as handle:
        data = tomllib.load(handle)

    return data["project"]["version"]


def debian_version(version: str) -> str:
    # Python pre-release: 0.1.0b1
    # Debian pre-release: 0.1.0~b1
    if "b" in version:
        base, beta = version.rsplit("b", 1)
        if beta.isdigit():
            return f"{base}~b{beta}"

    return version


def main() -> int:
    if not BUNDLE.is_dir():
        raise SystemExit(f"PyInstaller bundle not found: {BUNDLE}")

    if not ICON.is_file():
        raise SystemExit(f"Application icon not found: {ICON}")

    version = debian_version(project_version())
    architecture = "amd64"

    work = ROOT / "packaging" / "debian" / "build"
    package_root = work / "root"

    shutil.rmtree(work, ignore_errors=True)

    opt_dir = package_root / "opt" / "photo-album"
    bin_dir = package_root / "usr" / "bin"
    applications_dir = package_root / "usr" / "share" / "applications"
    icons_dir = (
        package_root
        / "usr"
        / "share"
        / "icons"
        / "hicolor"
        / "scalable"
        / "apps"
    )
    debian_dir = package_root / "DEBIAN"

    opt_dir.parent.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    applications_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)
    debian_dir.mkdir(parents=True, exist_ok=True)

    shutil.copytree(BUNDLE, opt_dir, dirs_exist_ok=True)
    shutil.copy2(DESKTOP, applications_dir / "photo-album.desktop")
    shutil.copy2(ICON, icons_dir / "photo-album.svg")

    for command, executable in (
        ("photo-album", "photo-album"),
        ("pa", "photo-album"),
        ("photo-album-cli", "photo-album-cli"),
    ):
        launcher = bin_dir / command
        launcher.write_text(
            "#!/bin/sh\n"
            f'exec /opt/photo-album/{executable} "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)

    control = debian_dir / "control"
    control.write_text(
        f"""Package: photo-album
Version: {version}
Section: graphics
Priority: optional
Architecture: {architecture}
Maintainer: Photo Album Contributors
Description: Create chronological photo albums
 A multilingual desktop application for creating chronological
 photo albums and exporting them as PDF documents.
""",
        encoding="utf-8",
    )

    output = ROOT / f"photo-album_{version}_{architecture}.deb"

    subprocess.run(
        [
            "dpkg-deb",
            "--root-owner-group",
            "--build",
            str(package_root),
            str(output),
        ],
        check=True,
    )

    print(f"Built: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
