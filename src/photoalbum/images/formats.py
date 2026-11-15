"""The application's accepted still-image formats (not every Pillow codec)."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageFormat:
    name: str
    extensions: tuple[str, ...]
    always_opaque: bool = False


FORMATS = (
    ImageFormat("JPEG", (".jpg", ".jpeg"), always_opaque=True),
    ImageFormat("PNG", (".png",)),
    ImageFormat("HEIF", (".heic", ".heif")),
    ImageFormat("WEBP", (".webp",)),
    ImageFormat("TIFF", (".tif", ".tiff")),
)
SUPPORTED_EXTENSIONS = frozenset(ext for fmt in FORMATS for ext in fmt.extensions)


def image_glob_patterns() -> str:
    return " ".join(f"*{ext}" for fmt in FORMATS for ext in fmt.extensions)


def is_guaranteed_opaque(filename: str | Path) -> bool:
    """Conservative layout hint; HEIF, PNG, TIFF and WebP can contain alpha."""
    extension = Path(filename).suffix.lower()
    return any(fmt.always_opaque and extension in fmt.extensions for fmt in FORMATS)
