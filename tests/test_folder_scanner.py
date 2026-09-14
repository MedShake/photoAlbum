from pathlib import Path

import pytest

from photoalbum.scanner import FolderScanner


def test_scans_supported_images(tmp_path: Path):
    (tmp_path / "photo1.jpg").touch()
    (tmp_path / "photo2.jpeg").touch()
    (tmp_path / "photo3.png").touch()
    (tmp_path / "notes.txt").touch()

    scanner = FolderScanner()
    results = scanner.scan(tmp_path)

    assert [path.name for path in results] == [
        "photo1.jpg",
        "photo2.jpeg",
        "photo3.png",
    ]


def test_extensions_are_case_insensitive(tmp_path: Path):
    (tmp_path / "photo1.JPG").touch()
    (tmp_path / "photo2.JPEG").touch()
    (tmp_path / "photo3.PNG").touch()

    scanner = FolderScanner()
    results = scanner.scan(tmp_path)

    assert len(results) == 3


def test_non_recursive_scan_ignores_subdirectories(
    tmp_path: Path,
):
    subdirectory = tmp_path / "holiday"
    subdirectory.mkdir()

    (tmp_path / "root.jpg").touch()
    (subdirectory / "nested.jpg").touch()

    scanner = FolderScanner()
    results = scanner.scan(
        tmp_path,
        recursive=False,
    )

    assert [path.name for path in results] == [
        "root.jpg",
    ]


def test_recursive_scan_includes_subdirectories(
    tmp_path: Path,
):
    subdirectory = tmp_path / "holiday"
    subdirectory.mkdir()

    (tmp_path / "root.jpg").touch()
    (subdirectory / "nested.jpg").touch()

    scanner = FolderScanner()
    results = scanner.scan(
        tmp_path,
        recursive=True,
    )

    assert len(results) == 2

    assert tmp_path / "root.jpg" in results
    assert subdirectory / "nested.jpg" in results


def test_results_are_sorted(tmp_path: Path):
    (tmp_path / "zebra.jpg").touch()
    (tmp_path / "Alpha.jpg").touch()
    (tmp_path / "middle.jpg").touch()

    scanner = FolderScanner()
    results = scanner.scan(tmp_path)

    assert [path.name for path in results] == [
        "Alpha.jpg",
        "middle.jpg",
        "zebra.jpg",
    ]


def test_missing_directory_raises_error(tmp_path: Path):
    missing = tmp_path / "missing"

    scanner = FolderScanner()

    with pytest.raises(FileNotFoundError):
        scanner.scan(missing)


def test_file_path_raises_error(tmp_path: Path):
    file_path = tmp_path / "photo.jpg"
    file_path.touch()

    scanner = FolderScanner()

    with pytest.raises(NotADirectoryError):
        scanner.scan(file_path)

