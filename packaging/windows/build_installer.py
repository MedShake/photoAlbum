"""Build the Windows installer with Inno Setup."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
ISS = ROOT / "packaging" / "windows" / "photo-album.iss"


def project_version() -> str:
    with PYPROJECT.open("rb") as handle:
        data = tomllib.load(handle)
    return data["project"]["version"]


def main() -> int:
    version = project_version()

    subprocess.run(
        [
            "ISCC.exe",
            f"/DAppVersion={version}",
            str(ISS),
        ],
        check=True,
    )

    print(f"Built Windows installer for Photo Album {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
