from photoalbum.gui.workers import (
    PdfExportWorker,
)


def test_pdf_export_worker_is_exported():
    assert PdfExportWorker is not None
