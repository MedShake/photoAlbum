"""Generate the Windows application icon from the master SVG."""

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parents[2]
SVG = ROOT / "src" / "photoalbum" / "resources" / "icons" / "photoalbum.svg"
OUTPUT = Path(__file__).resolve().parent / "photoalbum.ico"

SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_svg(size: int) -> Image.Image:
    svg_data = QByteArray(SVG.read_bytes())
    renderer = QSvgRenderer(svg_data)

    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG: {SVG}")

    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    ptr = image.constBits()
    raw = bytes(ptr[: image.sizeInBytes()])

    return Image.frombytes(
        "RGBA",
        (image.width(), image.height()),
        raw,
        "raw",
        "BGRA",
    )


def main() -> None:
    images = [render_svg(size) for size in SIZES]

    images[-1].save(
        OUTPUT,
        format="ICO",
        append_images=images[:-1],
        sizes=[(size, size) for size in SIZES],
    )

    print(f"Generated Windows icon: {OUTPUT}")


if __name__ == "__main__":
    main()
