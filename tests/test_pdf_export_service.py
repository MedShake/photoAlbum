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
