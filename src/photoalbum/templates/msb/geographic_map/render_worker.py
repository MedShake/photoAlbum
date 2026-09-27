from __future__ import annotations

from PySide6.QtCore import (
    QByteArray,
    QBuffer,
    QIODevice,
    QObject,
    QRectF,
    QRunnable,
    Signal,
)
from PySide6.QtGui import (
    QImage,
    QPainter,
)

from .composition import compose_geographic_map
from .rendering import paint_map


class GeographicMapRenderSignals(QObject):
    finished = Signal(
        str,
        bytes,
    )
    failed = Signal(
        str,
        str,
    )


class GeographicMapRenderWorker(QRunnable):
    """Rasterize a geographic-map preview outside the GUI thread."""

    def __init__(
        self,
        *,
        request_id: str,
        width: int,
        height: int,
        photos: tuple,
        year: int | None,
        options: dict,
    ) -> None:
        super().__init__()
        self.request_id = request_id
        self.width = width
        self.height = height
        self.photos = photos
        self.year = year
        self.options = options

        self.signals = GeographicMapRenderSignals()

    def run(self) -> None:
        try:
            composition = compose_geographic_map(self.photos, year=self.year)
            image = QImage(
                self.width,
                self.height,
                QImage.Format.Format_ARGB32,
            )

            image.fill(
                self.options["water_color"]
            )

            painter = QPainter(image)

            try:
                paint_map(
                    painter,
                    QRectF(0.0, 0.0, float(self.width), float(self.height)),
                    composition,
                    **self.options,
                )
            finally:
                painter.end()

            data = QByteArray()
            buffer = QBuffer(data)

            if not buffer.open(
                QIODevice.OpenModeFlag.WriteOnly
            ):
                raise RuntimeError(
                    "Unable to open geographic map preview buffer."
                )

            try:
                if not image.save(
                    buffer,
                    "PNG",
                ):
                    raise RuntimeError(
                        "Unable to encode geographic map preview."
                    )
            finally:
                buffer.close()

            result = bytes(data)

        except Exception as exc:
            try:
                self.signals.failed.emit(
                    self.request_id,
                    str(exc),
                )
            except RuntimeError:
                pass

            return

        try:
            self.signals.finished.emit(
                self.request_id,
                result,
            )
        except RuntimeError:
            pass
