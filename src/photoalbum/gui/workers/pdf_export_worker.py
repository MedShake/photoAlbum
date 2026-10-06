from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)

from photoalbum.export import PdfExportService
from photoalbum.i18n import Translator
from photoalbum.sources import SourceReconnectRequiredError


class PdfExportWorker(QObject):
    """
    Execute a PDF export outside the GUI thread.
    """

    progress = Signal(
        int,
        int,
        str,
    )

    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: PdfExportService,
        *,
        output_path: Path,
        result,
        settings,
        photos,
        page_width_mm: float,
        page_height_mm: float,
        dpi: int,
        metadata,
        content,
        prepare_assets=None,
        translator: Translator | None = None,
    ) -> None:
        super().__init__()

        self._service = service
        self._output_path = Path(
            output_path
        )

        self._arguments = {
            "result": result,
            "settings": settings,
            "photos": photos,
            "page_width_mm": page_width_mm,
            "page_height_mm": page_height_mm,
            "dpi": dpi,
            "metadata": metadata,
            "content": content,
        }
        self._prepare_assets = prepare_assets
        self._translator = translator or Translator("en")

    @Slot()
    def run(self) -> None:
        try:
            if self._prepare_assets is not None:
                self._prepare_assets(list(self._arguments["result"].template_photos))
            self._service.export(
                output_path=self._output_path,
                progress_callback=self._progress,
                **self._arguments,
            )
        except SourceReconnectRequiredError as exc:
            key = (
                "source.export.reconnect_required"
                if exc.operation == "export"
                else "source.asset.reconnect_required"
            )
            self.failed.emit(
                self._translator.tr(
                    key,
                    filename=exc.filename,
                )
            )
            return
        except Exception:
            self.failed.emit(
                self._translator.tr("render.generate_error")
            )
            return

        self.finished.emit(
            self._output_path
        )

    def _progress(
        self,
        current: int,
        total: int,
        message: str,
    ) -> None:
        self.progress.emit(
            current,
            total,
            message,
        )
