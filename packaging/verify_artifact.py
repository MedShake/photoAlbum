"""Check shipped resources against the source tree and smoke-test frozen GUIs.

Uses only the standard library, so verification cannot import resources from an
installed development copy and accidentally hide an incomplete artifact.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
from zipfile import ZipFile


SOURCE_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "photoalbum"


def package_resources(package: Path) -> dict[str, bytes]:
    resources = {}
    for path in package.rglob("*"):
        relative = path.relative_to(package)
        if (not path.is_file() or path.suffix in {".py", ".pyc", ".pyo"}
                or any(part.startswith(".") or part == "__pycache__" for part in relative.parts)):
            continue
        resources[f"photoalbum/{relative.as_posix()}"] = path.read_bytes()
    if not resources:
        raise ValueError(f"No resources found in {package}")
    return resources


def verify_resources(actual: dict[str, bytes], source: Path = SOURCE_PACKAGE) -> None:
    expected = package_resources(source)
    missing = sorted(expected.keys() - actual.keys())
    changed = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])
    if missing or changed:
        raise ValueError(f"Missing resources: {missing}; changed resources: {changed}")
    print(f"OK: {len(expected)} resources match the source package")


def verify_collected_resources(datas, source: Path = SOURCE_PACKAGE) -> None:
    """Validate PyInstaller's (source file, destination directory) collection."""
    actual = {
        (Path(destination) / Path(filename).name).as_posix(): Path(filename).read_bytes()
        for filename, destination in datas
    }
    verify_resources(actual, source)


def verify_artifact(artifact: Path, source: Path = SOURCE_PACKAGE) -> None:
    if artifact.is_dir():
        package = artifact / "_internal" / "photoalbum"
        verify_resources(package_resources(package), source)
    elif artifact.suffix == ".whl":
        with ZipFile(artifact) as archive:
            verify_resources({name: archive.read(name) for name in archive.namelist()
                              if name.startswith("photoalbum/") and not name.endswith("/")}, source)
    else:
        # Both sdists (<name>/src/photoalbum) and Linux bundles
        # (<name>/_internal/photoalbum) retain their package-relative paths.
        actual = {}
        with tarfile.open(artifact) as archive:
            for member in archive.getmembers():
                parts = PurePosixPath(member.name).parts
                if not member.isfile() or len(parts) < 4 or parts[1:3] not in (
                    ("src", "photoalbum"), ("_internal", "photoalbum"),
                ):
                    continue
                with archive.extractfile(member) as handle:
                    actual[PurePosixPath(*parts[2:]).as_posix()] = handle.read()
        verify_resources(actual, source)


def smoke_test(command: list[str]) -> None:
    """Require normal GUI initialization, a Qt event loop and a clean exit."""
    for language in ("fr", "en"):
        with tempfile.TemporaryDirectory(prefix="photoalbum-startup-") as directory:
            root = Path(directory)
            report = root / "started.txt"
            env = os.environ.copy()
            for key in ("PYTHONPATH", "PYTHONHOME"):
                env.pop(key, None)
            env.update(QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(root / "config"),
                       XDG_CACHE_HOME=str(root / "cache"), APPDATA=str(root / "config"),
                       LOCALAPPDATA=str(root / "cache"))
            result = subprocess.run(
                [*command, "--language", language, "--smoke-test", str(report)],
                cwd=root, env=env, capture_output=True, text=True, timeout=60,
            )
            if result.returncode:
                raise RuntimeError(f"GUI startup failed ({language}, exit {result.returncode}):\n"
                                   f"{result.stdout}\n{result.stderr}")
            if not report.is_file() or report.read_text(encoding="utf-8") != "ok\n":
                raise RuntimeError(f"GUI did not confirm startup ({language})")
            print(f"OK: GUI started and exited cleanly ({language})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", type=Path)
    parser.add_argument("--smoke-test", action="store_true", help="Also start each bundle's GUI in FR/EN")
    args = parser.parse_args()
    for artifact in args.artifacts:
        print(f"Verifying {artifact}")
        verify_artifact(artifact)
        if args.smoke_test:
            executable = artifact / ("photo-album.exe" if os.name == "nt" else "photo-album")
            if not artifact.is_dir() or not executable.is_file():
                raise ValueError("--smoke-test requires an application bundle directory")
            smoke_test([str(executable.resolve())])


if __name__ == "__main__":
    main()
