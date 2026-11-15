"""Compatibility imports; image metadata belongs to the image services layer."""
from photoalbum.images import ExifReader, ImageMetadata

__all__ = ["ExifReader", "ImageMetadata"]
