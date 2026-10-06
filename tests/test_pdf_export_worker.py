from pathlib import Path

from photoalbum.gui.workers import (
    PdfExportWorker,
)
from photoalbum.i18n import Translator
from photoalbum.sources import SourceReconnectRequiredError


def test_pdf_export_worker_is_exported():
    assert PdfExportWorker is not None


class _FakePdfExportService:
    def export(self, **kwargs):
        raise AssertionError("export must not start when source preparation fails")


class _Result:
    template_photos = ()


def test_pdf_export_worker_translates_reconnect_required_error():
    worker = PdfExportWorker(
        _FakePdfExportService(),
        output_path=Path("album.pdf"),
        result=_Result(),
        settings=None,
        photos=[],
        page_width_mm=210.0,
        page_height_mm=297.0,
        dpi=150,
        metadata=None,
        content=None,
        prepare_assets=lambda photos: (_ for _ in ()).throw(
            SourceReconnectRequiredError(
                filename="photo.jpg",
                source_id="synology-1",
                operation="export",
            )
        ),
        translator=Translator("fr"),
    )

    messages = []
    worker.failed.connect(messages.append)
    worker.run()

    assert messages == [
        "Reconnectez la source contenant « photo.jpg » avant de générer le PDF."
    ]


def test_pdf_export_worker_hides_raw_generic_exception_text():
    raw = "sqlite provider exploded"
    worker = PdfExportWorker(
        _FakePdfExportService(),
        output_path=Path("album.pdf"),
        result=_Result(),
        settings=None,
        photos=[],
        page_width_mm=210.0,
        page_height_mm=297.0,
        dpi=150,
        metadata=None,
        content=None,
        prepare_assets=lambda photos: (_ for _ in ()).throw(RuntimeError(raw)),
        translator=Translator("fr"),
    )

    messages = []
    worker.failed.connect(messages.append)
    worker.run()

    assert messages == ["Impossible de générer le PDF."]
    assert raw not in messages[0]
