from pathlib import Path

import pytest

from photoalbum.export import (
    PdfExportService,
    PdfMetadata,
)
from photoalbum.i18n import Translator


def test_pdf_metadata_defaults():
    metadata = PdfMetadata()

    assert metadata.title == ""
    assert metadata.author == ""
    assert metadata.subject == ""
    assert metadata.keywords == ""


def test_pdf_export_rejects_invalid_dpi(
    tmp_path: Path,
):
    service = PdfExportService(
        Translator("fr")
    )

    with pytest.raises(
        ValueError,
        match="DPI",
    ):
        service.export(
            output_path=tmp_path / "album.pdf",
            result=None,
            settings=None,
            photos=[],
            page_width_mm=210.0,
            page_height_mm=297.0,
            dpi=0,
        )


def test_pdf_export_rejects_invalid_page_size(
    tmp_path: Path,
):
    service = PdfExportService(
        Translator("fr")
    )

    with pytest.raises(
        ValueError,
        match="dimensions",
    ):
        service.export(
            output_path=tmp_path / "album.pdf",
            result=None,
            settings=None,
            photos=[],
            page_width_mm=0.0,
            page_height_mm=297.0,
            dpi=300,
        )


def test_pdf_export_accepts_progress_callback():
    import inspect

    parameters = inspect.signature(
        PdfExportService.export
    ).parameters

    assert "progress_callback" in parameters


def test_write_pdf_metadata_writes_document_properties(
    tmp_path,
):
    from pypdf import PdfReader, PdfWriter

    from photoalbum.export import (
        PdfExportService,
        PdfMetadata,
    )

    output_path = tmp_path / "metadata.pdf"

    writer = PdfWriter()
    writer.add_blank_page(
        width=595,
        height=842,
    )

    with output_path.open("wb") as stream:
        writer.write(stream)

    metadata = PdfMetadata(
        title="Photo Album metadata test",
        author="Test Author",
        subject="PDF metadata integration test",
        keywords="photo, album, geolocation, test",
    )

    PdfExportService._write_pdf_metadata(
        output_path,
        metadata,
    )

    reader = PdfReader(output_path)
    result = reader.metadata

    assert len(reader.pages) == 1
    assert result.title == "Photo Album metadata test"
    assert result.author == "Test Author"
    assert result.subject == "PDF metadata integration test"
    assert (
        result.get("/Keywords")
        == "photo, album, geolocation, test"
    )
    assert result.creator == "Photo Album"
