from __future__ import annotations

from pathlib import Path


class FolderScanner:
    SUPPORTED_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
    }

    def scan(
        self,
        directory: Path,
        recursive: bool = False,
    ) -> list[Path]:
        if not directory.exists():
            raise FileNotFoundError(
                f"Directory does not exist: {directory}"
            )

        if not directory.is_dir():
            raise NotADirectoryError(
                f"Path is not a directory: {directory}"
            )

        iterator = (
            directory.rglob("*")
            if recursive
            else directory.glob("*")
        )

        images = [
            path
            for path in iterator
            if path.is_file()
            and path.suffix.lower() in self.SUPPORTED_EXTENSIONS
        ]

        return sorted(
            images,
            key=lambda path: str(path).lower(),
        )

