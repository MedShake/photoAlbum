from __future__ import annotations

from pathlib import Path
import os


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

        # pathlib glob can silently skip unreadable directories. Abort before
        # changing the snapshot if any directory in the requested scan fails.
        images = []

        def visit(folder):
            with os.scandir(folder) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    if entry.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                        images.append(path)
                    elif recursive and entry.is_dir(follow_symlinks=False):
                        visit(path)

        visit(directory)

        return sorted(
            images,
            key=lambda path: str(path).lower(),
        )
