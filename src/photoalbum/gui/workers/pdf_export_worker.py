from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)

from photoalbum.export import PdfExportService


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

    @Slot()
    def run(self) -> None:
        try:
            if self._prepare_assets is not None:
                self._prepare_assets(self._arguments["photos"])
            self._service.export(
                output_path=self._output_path,
                progress_callback=self._progress,
                **self._arguments,
            )
        except Exception as exc:
            self.failed.emit(
                str(exc)
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
