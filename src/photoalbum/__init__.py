"""Photo Album package."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

try:
    __version__ = version("photo-album")
except PackageNotFoundError:
    # Fallback for unusual source-tree executions where the package
    # metadata is not available.
    __version__ = "0.1.0"

__all__ = ["__version__"]
