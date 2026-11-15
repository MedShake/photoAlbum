from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
from photoalbum.template_engine.api import decode_image

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
                rect = item.rect
                x, y = round(rect.x * self.width), round(rect.y * self.height)
                w = max(1, round(rect.width * self.width))
                h = max(1, round(rect.height * self.height))
                if item.photo is None or item.photo.path is None:
                    from PIL import ImageDraw
                    ImageDraw.Draw(canvas).rectangle((x, y, x + w - 1, y + h - 1), fill="black")
                    continue
                path = Path(item.photo.path)

                try:
                    with decode_image(path, (w, h)) as source:
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
                            source if source.mode == "RGBA" else None,
                        )

                except Exception:
                    from PIL import ImageDraw
                    ImageDraw.Draw(canvas).rectangle((x, y, x + w - 1, y + h - 1), fill="black")
                    continue

            buffer = BytesIO()

            canvas.save(
                buffer,
                format="PNG",
                optimize=False,
            )

            result = buffer.getvalue()

        except Exception as exc:
            try:
                self.signals.failed.emit(
                    self.request_id,
                    str(exc),
                )
            except RuntimeError:
                # The signals object may have been deleted
                # while this QRunnable was finishing.
                pass

            return

        try:
            self.signals.finished.emit(
                self.request_id,
                result,
            )
        except RuntimeError:
            # The preview owner may have disappeared while
            # this QRunnable was finishing. The rendered
            # result can simply be discarded.
            pass
