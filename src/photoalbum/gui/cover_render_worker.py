from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import (
    Image,
    ImageOps,
)
from PySide6.QtCore import (
    QObject,
    QRunnable,
    Signal,
)


class CoverRenderSignals(QObject):
    finished = Signal(
        str,
        bytes,
    )
    failed = Signal(
        str,
        str,
    )


class CoverRenderWorker(QRunnable):
    """
    Rasterize a complete scatter preview off the GUI thread.

    The worker deliberately returns PNG bytes rather than
    QPixmap: QPixmap belongs to the GUI thread.
    """

    def __init__(
        self,
        *,
        request_id: str,
        width: int,
        height: int,
        items,
    ) -> None:
        super().__init__()

        self.request_id = request_id
        self.width = width
        self.height = height
        self.items = tuple(items)

        self.signals = CoverRenderSignals()

    def run(self) -> None:
        try:
            canvas = Image.new(
                "RGB",
                (
                    self.width,
                    self.height,
                ),
                "white",
            )

            for item in self.items:
                path = Path(
                    item.photo.path
                )

                try:
                    with Image.open(path) as source:
                        source = (
                            ImageOps.exif_transpose(
                                source
                            )
                        )

                        source = source.convert(
                            "RGB"
                        )

                        rect = item.rect

                        x = round(
                            rect.x
                            * self.width
                        )
                        y = round(
                            rect.y
                            * self.height
                        )

                        w = max(
                            1,
                            round(
                                rect.width
                                * self.width
                            ),
                        )

                        h = max(
                            1,
                            round(
                                rect.height
                                * self.height
                            ),
                        )

                        source.thumbnail(
                            (w, h),
                            Image.Resampling.LANCZOS,
                        )

                        px = (
                            x
                            + (w - source.width) // 2
                        )
                        py = (
                            y
                            + (h - source.height) // 2
                        )

                        canvas.paste(
                            source,
                            (
                                px,
                                py,
                            ),
                        )

                except Exception:
                    # One broken image must not kill a
                    # complete cover preview.
                    continue

            buffer = BytesIO()

            canvas.save(
                buffer,
                format="PNG",
                optimize=False,
            )

            self.signals.finished.emit(
                self.request_id,
                buffer.getvalue(),
            )

        except Exception as exc:
            self.signals.failed.emit(
                self.request_id,
                str(exc),
            )
