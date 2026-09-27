"""Photo Album package."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

try:
    __version__ = version("photo-album")
except PackageNotFoundError:
    # Source tree used without installed package metadata.
    __version__ = "unknown"

__all__ = ["__version__"]
