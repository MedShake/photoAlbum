"""Qt boundary: transfer decoded pixels without an encoded intermediate file."""
import logging
from pathlib import Path

from PIL.Image import DecompressionBombError
from PySide6.QtCore import QSize
from PySide6.QtGui import QColorSpace, QImage

from photoalbum.images import decode_image


def load_qimage(path: str | Path | None, target_size: QSize | None = None, *, fit: str = "contain") -> QImage:
    try:
        if path is None or path == "":
            raise FileNotFoundError("Image path is missing")
        budget = (target_size.width(), target_size.height()) if target_size is not None else None
        with decode_image(path, budget, fit=fit) as image:
            mode = QImage.Format.Format_RGBA8888 if image.mode == "RGBA" else QImage.Format.Format_RGB888
            # copy() detaches Qt's storage from the temporary Python byte buffer.
            result = QImage(image.tobytes(), image.width, image.height,
                            image.width * len(image.getbands()), mode).copy()
            result.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.SRgb))
            return result
    except (OSError, ValueError, SyntaxError, RuntimeError, DecompressionBombError) as exc:
        logging.getLogger(__name__).warning("Could not decode image %s: %s", path, exc)
        return QImage()
